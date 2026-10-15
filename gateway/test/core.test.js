// 게이트웨이 핵심 시험: 이상한 값 처리, 알람, stale, 이력, 집계 (docs/11 4.2, 4.4, 9장)
import assert from 'node:assert/strict';
import test from 'node:test';
import { Gateway } from '../src/core.js';

const manifest = {
  version: 1,
  hall: 'hall01',
  sensors: [
    { sensorId: 'H01-RK01-TEMP-IN', topic: 'dct/v1/hall01/rack_01/temp_in', equipmentPath: '/DC/Hall01/Row01/Rack_01', equipmentType: 'rack', metric: 'temp_in', unit: 'degC', range: [10, 45], warn: 27, critical: 32 },
    { sensorId: 'H01-RK01-POWER', topic: 'dct/v1/hall01/rack_01/power', equipmentPath: '/DC/Hall01/Row01/Rack_01', equipmentType: 'rack', metric: 'power', unit: 'kW', range: [0, 15], warn: 10, critical: 13 },
    { sensorId: 'H01-CR01-FAN-SPEED', topic: 'dct/v1/hall01/crac_01/fan_speed', equipmentPath: '/DC/Hall01/Cooling/CRAC_01', equipmentType: 'crac', metric: 'fan_speed', unit: 'percent', range: [0, 100], warn: 20, critical: 5, direction: 'low' },
  ],
};
const T0 = Date.parse('2026-10-15T09:00:00.000Z');
const ts = (s) => new Date(T0 + s * 1000).toISOString();
const sample = (sensorId, s, value, unit) => ({ sensorId, ts: ts(s), value, unit });
const collect = (g, ev) => {
  const out = [];
  g.on(ev, (m) => out.push(m));
  return out;
};

test('정상 값은 latest에 들어가고 sample 이벤트가 나온다', () => {
  const g = new Gateway(manifest);
  const samples = collect(g, 'sample');
  g.ingest(sample('H01-RK01-TEMP-IN', 0, 24.6, 'degC'));
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').value, 24.6);
  assert.deepEqual(samples[0], { type: 'sample', sensorId: 'H01-RK01-TEMP-IN', value: 24.6, unit: 'degC', quality: 'good', ts: ts(0) });
});

test('주소로도 센서를 찾는다(MQTT)', () => {
  const g = new Gateway(manifest);
  g.ingestMqtt('dct/v1/hall01/rack_01/temp_in', JSON.stringify({ ts: ts(0), value: 25, unit: 'degC', quality: 'good' }));
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').value, 25);
});

test('범위 밖이면 품질 bad이고 알람은 판정하지 않는다', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  const samples = collect(g, 'sample');
  for (let i = 0; i < 4; i++) g.ingest(sample('H01-RK01-TEMP-IN', i, 60, 'degC'));
  assert.ok(samples.every((s) => s.quality === 'bad'));
  assert.equal(alarms.length, 0);
});

test('형식이 틀린 메시지, 단위가 다른 메시지, 모르는 센서는 버리고 다른 센서에는 영향이 없다', () => {
  const g = new Gateway(manifest);
  g.on('log', () => {});
  assert.equal(g.ingest(null), null);
  assert.equal(g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: 'nope', value: 1, unit: 'degC' }), null);
  assert.equal(g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: ts(0), value: '24', unit: 'degC' }), null);
  assert.equal(g.ingest(sample('H01-RK01-TEMP-IN', 0, 24, 'degF')), null);
  assert.equal(g.ingest(sample('H99-XX-NOPE', 0, 24, 'degC')), null);
  assert.equal(g.ingestMqtt('dct/v1/hall01/rack_01/temp_in', '{깨진 JSON'), null);
  assert.deepEqual(g.dropped, { format: 4, unit: 1, unknown: 1 }); // 형식 오류: null, 시각, 값 형식, 깨진 JSON
  assert.ok(g.ingest(sample('H01-RK01-POWER', 0, 7, 'kW')));
});

test('알람: 2번 연속이어야 주의, 내려갈 때는 히스테리시스', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  const feed = (s, v) => g.ingest(sample('H01-RK01-TEMP-IN', s, v, 'degC'));
  feed(0, 28); assert.equal(alarms.length, 0);
  feed(1, 28); assert.deepEqual(alarms.map((a) => [a.from, a.to]), [['normal', 'warn']]);
  feed(2, 26.8); feed(3, 26.6); assert.equal(alarms.length, 1);
  feed(4, 26.4); assert.deepEqual(alarms.map((a) => [a.from, a.to]), [['normal', 'warn'], ['warn', 'normal']]);
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').alarm, 'normal');
});

test('낮을수록 위험한 센서(팬 속도)', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  g.ingest(sample('H01-CR01-FAN-SPEED', 0, 100, 'percent'));
  g.ingest(sample('H01-CR01-FAN-SPEED', 1, 10, 'percent'));
  g.ingest(sample('H01-CR01-FAN-SPEED', 2, 10, 'percent'));
  assert.deepEqual(alarms.map((a) => a.to), ['warn']);
});

test('센서가 5초 넘게 값을 보내지 않으면 stale로 알리고 마지막 값은 유지한다', () => {
  const g = new Gateway(manifest);
  const samples = collect(g, 'sample');
  g.ingest(sample('H01-RK01-TEMP-IN', 0, 24, 'degC'));
  for (let s = 1; s <= 8; s++) g.ingest(sample('H01-RK01-POWER', s, 7, 'kW')); // 다른 센서만 값을 보낸다
  const stale = samples.filter((m) => m.sensorId === 'H01-RK01-TEMP-IN' && m.quality === 'stale');
  assert.equal(stale.length, 1);
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').value, 24);
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').quality, 'stale');
  g.ingest(sample('H01-RK01-TEMP-IN', 9, 24.5, 'degC')); // 다시 오면 정상으로 돌아온다
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').quality, 'good');
});

test('이력은 보관 시간이 지나면 지운다', () => {
  const g = new Gateway(manifest, { historyMinutes: 1 });
  for (let s = 0; s <= 120; s++) g.ingest(sample('H01-RK01-POWER', s, 7, 'kW'));
  const h = g.historyOf('H01-RK01-POWER');
  assert.ok(h.length >= 60 && h.length <= 62, `길이 ${h.length}`);
  assert.equal(g.historyOf('없는센서'), null);
  assert.equal(g.historyOf('H01-RK01-POWER', 0.5).length <= 32, true);
});

test('집계: IT 전력, PUE, 누적 전력량', () => {
  const g = new Gateway(manifest);
  const aggs = collect(g, 'aggregate');
  g.ingest(sample('H01-CR01-FAN-SPEED', 0, 100, 'percent'));
  for (let s = 1; s <= 5; s++) {
    g.ingest(sample('H01-RK01-POWER', s, 8, 'kW'));
    g.ingest(sample('H01-CR01-FAN-SPEED', s, 100, 'percent'));
  }
  const last = (n) => [...aggs].reverse().find((a) => a.name === n);
  assert.equal(last('it_power').value, 8);
  assert.ok(last('pue').value > 1);
  assert.ok(last('energy_kwh').value > 0);
  assert.ok(last('cooling_power').unit === 'kW');
});

test('snapshot에는 모든 센서의 최근 값과 알람 상태, 시나리오가 들어 있다', () => {
  const g = new Gateway(manifest);
  g.scenarioEvent({ type: 'scenario', event: 'start', name: 'cooling_failure', ts: ts(0) });
  g.ingest(sample('H01-RK01-POWER', 1, 7, 'kW'));
  const snap = g.snapshot();
  assert.equal(snap.type, 'snapshot');
  assert.equal(snap.scenario, 'cooling_failure');
  assert.equal(snap.sensors.length, 1);
  assert.equal(snap.sensors[0].alarm, 'normal');
});
