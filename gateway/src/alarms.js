// 알람 판정 규칙 (docs/11 4.4장). 생성기(Python, sim/sensors/dct_sensors/alarms.py)와 같은 규칙이다.
// 어긋나지 않도록 sim/sensors/tests/alarm_vectors.json을 둘이 함께 쓴다.
//
// - 올라갈 때: 기준을 넘은 상태가 consecutive번 연속일 때만 올린다. 연속하는 동안 가장 낮은 단계로 올린다.
// - 내려갈 때: 바로 반영하되, 기준에서 hysteresis만큼 더 내려와야 그 단계를 벗어난다.
// - 기준이 없으면(warn, critical 모두 null) 판정하지 않는다.
// - direction이 "low"이면 값이 낮을수록 위험하다(부호를 바꿔 같은 규칙으로 처리한다).

export const NAMES = ['normal', 'warn', 'critical'];
const LEVELS = Object.fromEntries(NAMES.map((n, i) => [n, i]));

export class AlarmState {
  constructor({ warn = null, critical = null, direction = 'high', hysteresis = 0.5, consecutive = 2 } = {}) {
    this.warn = warn;
    this.critical = critical;
    this.direction = direction;
    this.hysteresis = hysteresis;
    this.consecutive = consecutive;
    this.state = 'normal';
    this.run = 0;
    this.runMin = 0;
  }

  #thresholds() {
    const sgn = this.direction === 'high' ? 1 : -1;
    return [this.warn == null ? null : sgn * this.warn, this.critical == null ? null : sgn * this.critical, sgn];
  }

  #rawLevel(value) {
    const [w, c, sgn] = this.#thresholds();
    const v = value * sgn;
    if (c != null && v >= c) return 2;
    if (w != null && v >= w) return 1;
    return 0;
  }

  #holdLevel(value) {
    const [w, c, sgn] = this.#thresholds();
    const v = value * sgn;
    const cur = LEVELS[this.state];
    let lvl = 0;
    if (cur >= 1 && w != null && v > w - this.hysteresis) lvl = 1;
    if (cur === 2 && c != null && v > c - this.hysteresis) lvl = 2;
    return lvl;
  }

  // 새 값을 넣고, 상태가 바뀌면 [이전, 새 상태]를, 아니면 null을 돌려준다.
  update(value) {
    const cur = LEVELS[this.state];
    const raw = this.#rawLevel(value);
    let next;
    if (raw > cur) {
      this.run += 1;
      this.runMin = this.run === 1 ? raw : Math.min(this.runMin, raw);
      if (this.run < this.consecutive) return null;
      next = this.runMin;
      this.run = 0;
      this.runMin = 0;
    } else {
      this.run = 0;
      this.runMin = 0;
      const hold = this.#holdLevel(value);
      if (hold >= cur) return null;
      next = hold;
    }
    const old = this.state;
    this.state = NAMES[next];
    return [old, this.state];
  }
}

// 값이 범위 밖이면 bad, 아니면 good (docs/11 4.2장)
export function qualityFor(value, [lo, hi]) {
  return value >= lo && value <= hi ? 'good' : 'bad';
}
