// 알람 판정 규칙 시험. 생성기(Python)와 같은 시험 자료를 쓴다: sim/sensors/tests/alarm_vectors.json
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { AlarmState, qualityFor } from '../src/alarms.js';

const vectors = JSON.parse(fs.readFileSync(new URL('../../sim/sensors/tests/alarm_vectors.json', import.meta.url), 'utf8'));

for (const c of vectors.cases) {
  test(`알람 규칙: ${c.name}`, () => {
    const a = new AlarmState({ warn: c.warn, critical: c.critical, direction: c.direction, hysteresis: c.hysteresis, consecutive: c.consecutive });
    const got = [];
    c.values.forEach((v, index) => {
      const tr = a.update(v);
      if (tr) got.push({ index, from: tr[0], to: tr[1] });
    });
    assert.deepEqual(got, c.transitions);
  });
}

test('범위 밖이면 bad', () => {
  assert.equal(qualityFor(24, [10, 45]), 'good');
  assert.equal(qualityFor(60, [10, 45]), 'bad');
});
