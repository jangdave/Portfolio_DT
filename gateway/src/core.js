// 게이트웨이의 핵심: 센서 값을 받아 검증하고, 알람을 판정하고, 이력과 집계를 만든다. (docs/11 4, 5, 9장)
// 네트워크(MQTT, WebSocket)와 분리해 두어서 Node 내장 시험으로 바로 검증할 수 있다.
import { EventEmitter } from 'node:events';
import { AlarmState, qualityFor } from './alarms.js';

export const DEFAULT_CONFIG = {
  historyMinutes: 15,   // 이력 보관(메모리)
  staleMs: 5000,        // 이 시간(센서 시각 기준) 동안 값이 없으면 stale
  hysteresis: 0.5,
  consecutive: 2,
  // 집계 추정식(docs/11 9장). 합성 추정이며 실제 시설의 효율 계산이 아니다.
  fanPowerKw: 3.0,
  coolingBaseKw: 1.0,
  lossRatio: 0.06,
};

const parseTs = (ts) => {
  const t = Date.parse(ts);
  return Number.isFinite(t) ? t : null;
};
const iso = (ms) => new Date(ms).toISOString();

export class Gateway extends EventEmitter {
  constructor(manifest, config = {}) {
    super();
    this.manifest = manifest;
    this.cfg = { ...DEFAULT_CONFIG, ...config };
    this.byId = new Map(manifest.sensors.map((s) => [s.sensorId, s]));
    this.byTopic = new Map(manifest.sensors.map((s) => [s.topic, s]));
    this.latest = new Map();        // sensorId -> { value, unit, quality, ts, alarm }
    this.history = new Map(manifest.sensors.map((s) => [s.sensorId, []]));
    this.alarms = new Map(manifest.sensors.map((s) => [s.sensorId, new AlarmState({ ...s, direction: s.direction ?? 'high', hysteresis: this.cfg.hysteresis, consecutive: this.cfg.consecutive })]));
    this.lastSeenMs = new Map();    // sensorId -> 마지막 값의 시각(ms)
    this.nowMs = 0;                 // 지금까지 본 가장 늦은 센서 시각(재생해도 같은 판정이 나오게 센서 시각을 시계로 쓴다)
    this.scenario = null;
    this.aggregates = {};
    this.energyKwh = 0;
    this._lastAggMs = null;
    this.dropped = { format: 0, unit: 0, unknown: 0 };
    this.racks = manifest.sensors.filter((s) => s.equipmentType === 'rack' && s.metric === 'power');
    this.fans = manifest.sensors.filter((s) => s.metric === 'fan_speed');
  }

  log(msg) {
    this.emit('log', msg);
  }

  // 센서 값 한 건을 넣는다. { sensorId | topic, ts, value, unit, quality? }
  ingest(raw) {
    if (!raw || typeof raw !== 'object') return this.#drop('format', raw);
    const sensor = this.byId.get(raw.sensorId) ?? this.byTopic.get(raw.topic);
    if (!sensor) return this.#drop('unknown', raw);
    const tsMs = parseTs(raw.ts);
    if (tsMs == null || typeof raw.value !== 'number' || !Number.isFinite(raw.value) || typeof raw.unit !== 'string') return this.#drop('format', raw);
    if (raw.unit !== sensor.unit) return this.#drop('unit', raw);

    if (tsMs > this.nowMs) {
      this.#advanceClock(tsMs);
    }
    let quality = raw.quality === 'bad' ? 'bad' : qualityFor(raw.value, sensor.range ?? [-Infinity, Infinity]);
    const prev = this.latest.get(sensor.sensorId);
    const entry = { sensorId: sensor.sensorId, value: raw.value, unit: sensor.unit, quality, ts: iso(tsMs), alarm: prev?.alarm ?? 'normal' };
    this.latest.set(sensor.sensorId, entry);
    this.lastSeenMs.set(sensor.sensorId, tsMs);

    const hist = this.history.get(sensor.sensorId);
    hist.push({ ts: entry.ts, value: raw.value, quality });
    const cutoff = tsMs - this.cfg.historyMinutes * 60000;
    while (hist.length && parseTs(hist[0].ts) < cutoff) hist.shift();

    this.emit('sample', { type: 'sample', sensorId: sensor.sensorId, value: raw.value, unit: sensor.unit, quality, ts: entry.ts });
    if (quality === 'good') {
      const tr = this.alarms.get(sensor.sensorId).update(raw.value);
      if (tr) {
        entry.alarm = tr[1];
        this.emit('alarm', { type: 'alarm', sensorId: sensor.sensorId, from: tr[0], to: tr[1], value: raw.value, ts: entry.ts });
      }
    }
    return entry;
  }

  // MQTT 메시지(주소와 JSON 문자열 또는 객체)를 넣는다
  ingestMqtt(topic, payload) {
    let obj = payload;
    if (typeof payload === 'string' || Buffer.isBuffer(payload)) {
      try {
        obj = JSON.parse(payload.toString());
      } catch {
        return this.#drop('format', { topic, payload: String(payload).slice(0, 80) });
      }
    }
    return this.ingest({ ...obj, topic });
  }

  scenarioEvent(msg) {
    this.scenario = msg.event === 'start' ? msg.name : msg.event === 'end' ? null : this.scenario;
    if (msg.event === 'start' || msg.event === 'end') {
      this.emit('scenario', { type: 'scenario', name: msg.name, event: msg.event, ts: msg.ts });
    }
  }

  // 센서 시각이 앞으로 갈 때마다 stale 검사와 집계 갱신을 한다(초 단위).
  #advanceClock(tsMs) {
    this.nowMs = tsMs;
    for (const [id, seen] of this.lastSeenMs) {
      const e = this.latest.get(id);
      if (e && e.quality !== 'stale' && tsMs - seen > this.cfg.staleMs) {
        e.quality = 'stale';
        this.emit('sample', { type: 'sample', sensorId: id, value: e.value, unit: e.unit, quality: 'stale', ts: iso(tsMs) });
      }
    }
    if (this._lastAggMs == null || tsMs - this._lastAggMs >= 1000) this.#updateAggregates(tsMs);
  }

  #updateAggregates(tsMs) {
    const cfg = this.cfg;
    let it = 0;
    for (const s of this.racks) it += this.latest.get(s.sensorId)?.value ?? 0;
    let fanSum = 0;
    for (const s of this.fans) fanSum += (this.latest.get(s.sensorId)?.value ?? 100) / 100;
    const nCrac = new Set(this.fans.map((s) => s.equipmentPath)).size;
    const cooling = nCrac * cfg.coolingBaseKw + cfg.fanPowerKw * fanSum;
    const facility = it + cooling + it * cfg.lossRatio;
    if (this._lastAggMs != null) this.energyKwh += (facility * (tsMs - this._lastAggMs)) / 3600000;
    this._lastAggMs = tsMs;
    const next = {
      it_power: [it, 'kW'], cooling_power: [cooling, 'kW'], facility_power: [facility, 'kW'],
      pue: [it > 0 ? facility / it : 0, ''], energy_kwh: [this.energyKwh, 'kWh'],
    };
    for (const [name, [value, unit]] of Object.entries(next)) {
      const v = Math.round(value * 10000) / 10000;
      this.aggregates[name] = { name, value: v, unit, ts: iso(tsMs) };
      this.emit('aggregate', { type: 'aggregate', name, value: v, unit, ts: iso(tsMs) });
    }
  }

  #drop(kind, raw) {
    this.dropped[kind] += 1;
    this.log(`버린 메시지(${kind}): ${JSON.stringify(raw)?.slice(0, 120)}`);
    return null;
  }

  // 접속 직후 한 번 보내는 전체 상태 (docs/11 4.3장)
  snapshot() {
    return {
      type: 'snapshot',
      ts: this.nowMs ? iso(this.nowMs) : null,
      scenario: this.scenario,
      sensors: [...this.latest.values()],
      aggregates: this.aggregates,
    };
  }

  historyOf(sensorId, minutes = this.cfg.historyMinutes) {
    const hist = this.history.get(sensorId);
    if (!hist) return null;
    const cutoff = this.nowMs - minutes * 60000;
    return hist.filter((h) => parseTs(h.ts) >= cutoff);
  }
}
