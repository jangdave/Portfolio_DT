// 게이트웨이 핵심 시험: 이상한 값 처리, 알람, stale, 이력, 집계, 시각 처리 (docs/11 4.2, 4.4, 9장)
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
const quiet = (g) => {
  g.on('log', () => {});
  return g;
};

test('정상 값은 latest에 들어가고 sample 이벤트가 나온다', () => {
  const g = new Gateway(manifest);
  const samples = collect(g, 'sample');
  g.ingest(sample('H01-RK01-TEMP-IN', 0, 24.6, 'degC'));
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').value, 24.6);
  assert.deepEqual(samples[0], { type: 'sample', sensorId: 'H01-RK01-TEMP-IN', value: 24.6, unit: 'degC', quality: 'good', ts: ts(0) });
});

test('주소로도 센서를 찾는다(MQTT). 페이로드의 sensorId는 무시하고 주소로만 정한다', () => {
  const g = new Gateway(manifest);
  g.ingestMqtt('dct/v1/hall01/rack_01/temp_in', JSON.stringify({ ts: ts(0), value: 25, unit: 'degC', quality: 'good' }));
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').value, 25);
  // 주소는 rack_01 전력인데 페이로드가 다른 센서 ID를 주장해도 주소가 이긴다
  g.ingestMqtt('dct/v1/hall01/rack_01/power', { sensorId: 'H01-CR01-FAN-SPEED', ts: ts(1), value: 7, unit: 'kW' });
  assert.equal(g.latest.get('H01-RK01-POWER').value, 7);
  assert.equal(g.latest.has('H01-CR01-FAN-SPEED'), false);
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
  const g = quiet(new Gateway(manifest));
  assert.equal(g.ingest(null), null);
  assert.equal(g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: 'nope', value: 1, unit: 'degC' }), null);
  assert.equal(g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: ts(0), value: '24', unit: 'degC' }), null);
  assert.equal(g.ingest(sample('H01-RK01-TEMP-IN', 0, 24, 'degF')), null);
  assert.equal(g.ingest(sample('H99-XX-NOPE', 0, 24, 'degC')), null);
  assert.equal(g.ingestMqtt('dct/v1/hall01/rack_01/temp_in', '{깨진 JSON'), null);
  assert.deepEqual({ format: g.dropped.format, unit: g.dropped.unit, unknown: g.dropped.unknown }, { format: 4, unit: 1, unknown: 1 }); // 형식 오류: null, 시각, 값 형식, 깨진 JSON
  assert.ok(g.ingest(sample('H01-RK01-POWER', 0, 7, 'kW')));
});

test('시각은 UTC ISO 8601(밀리초, Z)이어야 한다. 시간대 없는 시각과 숫자 문자열은 버린다', () => {
  const g = quiet(new Gateway(manifest));
  for (const bad of ['2026-10-15T09:00:06.000', '5', '2026-10-15 09:00:06Z', '2026-10-15T09:00:06+09:00', 1760000000000]) {
    assert.equal(g.ingest({ sensorId: 'H01-RK01-POWER', ts: bad, value: 7, unit: 'kW' }), null, String(bad));
  }
  assert.ok(g.ingest({ sensorId: 'H01-RK01-POWER', ts: '2026-10-15T09:00:06Z', value: 7, unit: 'kW' })); // 밀리초 생략은 허용
  assert.equal(g.dropped.format, 5);
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

test('알람: 범위 밖(bad) 샘플이 끼면 연속이 끊긴다', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  const feed = (s, v) => g.ingest(sample('H01-RK01-TEMP-IN', s, v, 'degC'));
  feed(0, 28); feed(1, 100); feed(2, 28); // 28, 범위 밖, 28은 연속이 아니다
  assert.equal(alarms.length, 0);
  feed(3, 28);
  assert.deepEqual(alarms.map((a) => a.to), ['warn']);
});

test('알람: 중간에 stale이 되면 연속이 끊긴다', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  g.ingest(sample('H01-RK01-TEMP-IN', 0, 28, 'degC'));
  for (let s = 1; s <= 8; s++) g.ingest(sample('H01-RK01-POWER', s, 7, 'kW')); // 이 센서가 5초 넘게 끊겨 stale
  g.ingest(sample('H01-RK01-TEMP-IN', 9, 28, 'degC'));
  assert.equal(alarms.filter((a) => a.sensorId === 'H01-RK01-TEMP-IN').length, 0);
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

test('모든 센서가 동시에 끊겨도 heartbeat이 수신 시각만큼 시계를 밀어서 stale을 알린다', () => {
  const g = new Gateway(manifest);
  const samples = collect(g, 'sample');
  g.ingest(sample('H01-RK01-TEMP-IN', 10, 24, 'degC'));
  g.ingest(sample('H01-RK01-POWER', 10, 7, 'kW'));
  const wall = g.lastWallMs;
  g.heartbeat(wall + 3000);
  assert.equal(samples.filter((m) => m.quality === 'stale').length, 0); // 3초는 아직
  g.heartbeat(wall + 6500);
  assert.equal(samples.filter((m) => m.quality === 'stale').length, 2);
  assert.equal(g.latest.get('H01-RK01-POWER').quality, 'stale');
});

test('게이트웨이가 낸 stale 샘플을 다시 넣어도(녹화 재생) 정상 값으로 되돌아가지 않고 이력, 알람에 들어가지 않는다', () => {
  const g = new Gateway(manifest);
  g.ingest(sample('H01-RK01-TEMP-IN', 0, 24, 'degC'));
  for (let s = 1; s <= 8; s++) g.ingest(sample('H01-RK01-POWER', s, 7, 'kW'));
  const before = g.history.get('H01-RK01-TEMP-IN').length;
  g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: ts(8), value: 24, unit: 'degC', quality: 'stale' });
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').quality, 'stale');
  assert.equal(g.history.get('H01-RK01-TEMP-IN').length, before);
  assert.equal(g.dropped.stale, 1);
});

test('미래로 크게 튄 시각 하나가 시계를 멈추지 않는다', () => {
  const g = quiet(new Gateway(manifest));
  g.ingest(sample('H01-RK01-POWER', 0, 7, 'kW'));
  assert.equal(g.ingest({ sensorId: 'H01-RK01-TEMP-IN', ts: '2099-01-01T00:00:00.000Z', value: 24, unit: 'degC' }), null);
  assert.equal(g.dropped.jump, 1);
  for (let s = 1; s <= 13; s++) g.ingest(sample('H01-RK01-TEMP-IN', s, 24, 'degC'));
  assert.equal(g.historyOf('H01-RK01-TEMP-IN').length, 13); // 이력이 정상으로 쌓인다
  assert.equal(g.latest.get('H01-RK01-POWER').quality, 'stale'); // stale 판정도 계속 된다
});

test('같은 센서에서 시각이 뒤로 가는 샘플은 버린다', () => {
  const g = quiet(new Gateway(manifest));
  g.ingest(sample('H01-RK01-POWER', 10, 7, 'kW'));
  assert.equal(g.ingest(sample('H01-RK01-POWER', 5, 9, 'kW')), null);
  assert.equal(g.dropped.late, 1);
  assert.equal(g.latest.get('H01-RK01-POWER').value, 7);
  assert.equal(g.latest.get('H01-RK01-POWER').ts, ts(10));
  assert.equal(g.historyOf('H01-RK01-POWER').length, 1);
});

test('생성기가 다시 시작되어 시각이 크게 과거로 돌아가면 상태를 처음부터 다시 시작한다', () => {
  const g = quiet(new Gateway(manifest));
  const alarms = collect(g, 'alarm');
  for (let s = 100; s < 200; s++) g.ingest(sample('H01-RK01-TEMP-IN', s, 28, 'degC')); // 알람 상태가 된다
  assert.equal(g.latest.get('H01-RK01-TEMP-IN').alarm, 'warn');
  for (let s = 0; s < 4; s++) g.ingest(sample('H01-RK01-TEMP-IN', s, 28, 'degC')); // 100초 넘게 과거로: 재시작
  assert.equal(g.historyOf('H01-RK01-TEMP-IN').length, 4);
  assert.deepEqual(alarms.map((a) => a.to), ['warn', 'warn']); // 처음부터 다시 판정되어 알람이 다시 나온다
});

test('같은 시나리오를 두 번 재생해도 두 번째에 시계, 집계, 알람이 다시 움직인다(시나리오 시작이 상태를 초기화)', () => {
  const g = new Gateway(manifest);
  const alarms = collect(g, 'alarm');
  const aggs = collect(g, 'aggregate');
  const play = () => {
    g.scenarioEvent({ type: 'scenario', event: 'start', name: 'demo', ts: ts(0) });
    for (let s = 0; s < 6; s++) {
      g.ingest(sample('H01-RK01-TEMP-IN', s, s < 2 ? 24 : 28, 'degC'));
      g.ingest(sample('H01-RK01-POWER', s, 8, 'kW'));
      g.ingest(sample('H01-CR01-FAN-SPEED', s, 100, 'percent'));
    }
    g.scenarioEvent({ type: 'scenario', event: 'end', name: 'demo', ts: ts(6) });
  };
  play();
  const first = { alarms: alarms.length, energy: g.energyKwh, hist: g.historyOf('H01-RK01-POWER').length };
  play();
  assert.equal(alarms.length, first.alarms * 2);
  assert.equal(g.energyKwh, first.energy); // 두 번째도 처음부터 누적
  assert.equal(g.historyOf('H01-RK01-POWER').length, first.hist); // 이력이 두 배로 쌓이지 않는다
  assert.equal(aggs.length, 2 * 6 * 5);
});

test('이력은 보관 시간이 지나면 지우고, 센서의 마지막 값 시각을 기준으로 돌려준다', () => {
  const g = new Gateway(manifest, { historyMinutes: 1 });
  for (let s = 0; s <= 120; s++) g.ingest(sample('H01-RK01-POWER', s, 7, 'kW'));
  const h = g.historyOf('H01-RK01-POWER');
  assert.ok(h.length >= 60 && h.length <= 62, `길이 ${h.length}`);
  assert.equal(g.historyOf('없는센서'), null);
  assert.equal(g.historyOf('H01-RK01-POWER', 0.5).length <= 32, true);
  assert.deepEqual(g.historyOf('H01-RK01-TEMP-IN'), []); // 값이 없는 센서는 빈 이력
});

test('집계: 그 시각의 값으로 계산하고(첫 시각도 0이 아님), 마지막 시각은 flush로 확정한다', () => {
  const g = new Gateway(manifest);
  const aggs = collect(g, 'aggregate');
  for (let s = 0; s <= 4; s++) {
    g.ingest(sample('H01-RK01-POWER', s, 8, 'kW'));
    g.ingest(sample('H01-CR01-FAN-SPEED', s, 100, 'percent'));
  }
  const power = () => aggs.filter((a) => a.name === 'it_power');
  assert.equal(power().length, 4); // 마지막(4초)은 아직 확정 전
  assert.equal(power()[0].value, 8); // 첫 시각의 값
  assert.equal(power()[0].ts, ts(0));
  g.flush();
  assert.equal(power().length, 5);
  assert.equal(power()[4].ts, ts(4));
  const last = (n) => [...aggs].reverse().find((a) => a.name === n);
  assert.ok(last('pue').value > 1);
  assert.ok(last('cooling_power').unit === 'kW');
  // 누적 전력량: 시설 전력 x 1초 x 5번
  const facility = last('facility_power').value;
  assert.ok(Math.abs(last('energy_kwh').value - (facility * 5) / 3600) < 1e-3);
});

test('snapshot에는 매니페스트의 모든 센서가 들어 있다(값이 없는 센서는 value null, quality stale)', () => {
  const g = new Gateway(manifest);
  g.scenarioEvent({ type: 'scenario', event: 'start', name: 'cooling_failure', ts: ts(0) });
  g.ingest(sample('H01-RK01-POWER', 1, 7, 'kW'));
  const snap = g.snapshot();
  assert.equal(snap.type, 'snapshot');
  assert.equal(snap.scenario, 'cooling_failure');
  assert.equal(snap.sensors.length, 3);
  assert.equal(snap.sensors.find((s) => s.sensorId === 'H01-RK01-POWER').value, 7);
  const empty = snap.sensors.find((s) => s.sensorId === 'H01-RK01-TEMP-IN');
  assert.deepEqual([empty.value, empty.quality, empty.ts, empty.alarm], [null, 'stale', null, 'normal']);
});

test('보정 모델이 붙인 구간과 신뢰 등급은 형식이 맞을 때만 sample과 latest에 실리고, 값 판정에는 영향이 없다', () => {
  const g = new Gateway(manifest);
  const samples = collect(g, 'sample');
  g.ingest({ ...sample('H01-RK01-TEMP-IN', 0, 24.6, 'degC'), lower: 24.0, upper: 25.4, confidence: 'caution' });
  g.ingest({ ...sample('H01-RK01-TEMP-IN', 1, 24.7, 'degC'), lower: 26.0, upper: 25.0, confidence: 'great' }); // 구간 순서가 거꾸로, 모르는 등급
  assert.deepEqual([samples[0].lower, samples[0].upper, samples[0].confidence], [24.0, 25.4, 'caution']);
  assert.equal(samples[1].lower, undefined);
  assert.equal(samples[1].confidence, undefined);
  assert.equal(samples[1].quality, 'good');
  g.ingest({ ...sample('H01-RK01-TEMP-IN', 2, 24.8, 'degC'), lower: 24.1, upper: 25.5, confidence: 'ok' });
  assert.equal(g.snapshot().sensors.find((s) => s.sensorId === 'H01-RK01-TEMP-IN').confidence, 'ok');
});
