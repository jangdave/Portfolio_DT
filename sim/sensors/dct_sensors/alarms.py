"""알람 판정과 값 품질 규칙 (11 데이터 규격 4.2, 4.4장).

게이트웨이가 같은 규칙을 구현한다. 어긋나지 않도록 시험 자료(`tests/alarm_vectors.json`)를 둘이 함께 쓴다.

- 올라갈 때: 값이 기준을 넘은 상태가 `consecutive`번 연속일 때만 상태를 올린다(순간 튐 방지).
  연속하는 동안 가장 낮았던 단계로 올린다(한 번만 높게 튄 값으로 위험까지 올리지 않음).
- 내려갈 때: 바로 반영하되, 기준에서 `hysteresis`만큼 더 내려와야 그 단계를 벗어난다(기준 근처에서 알람이 깜빡이지 않게).
- 기준이 없으면(`warn`, `critical` 모두 None) 알람을 판정하지 않는다.
- `direction`이 "low"이면 값이 낮을수록 위험하다(예: 팬 속도). 내부에서 부호를 바꿔 같은 규칙으로 처리한다.
- 값이 `range` 밖이면 품질을 bad로 바꾸고 알람은 판정하지 않는다(`quality_for`).
- 품질이 good이 아닌 샘플(bad, stale)이 끼면 연속이 끊긴 것으로 본다(`break_run`). 그 사이에 값이 없었으므로 "연속 2번"이 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NAMES = ["normal", "warn", "critical"]
LEVELS = {n: i for i, n in enumerate(NAMES)}


@dataclass
class AlarmState:
    """센서 하나의 알람 상태기계."""

    warn: float | None
    critical: float | None
    direction: str = "high"
    hysteresis: float = 0.5
    consecutive: int = 2
    state: str = "normal"
    _run: int = field(default=0, repr=False)
    _run_min: int = field(default=0, repr=False)

    def _thresholds(self) -> tuple[float | None, float | None, float]:
        """부호를 맞춘 (주의, 위험, 값 부호). direction이 low이면 값에 -1을 곱해 '높을수록 위험'으로 바꾼다."""
        sgn = 1.0 if self.direction == "high" else -1.0
        w = None if self.warn is None else sgn * self.warn
        c = None if self.critical is None else sgn * self.critical
        return w, c, sgn

    def _raw_level(self, v: float) -> int:
        w, c, sgn = self._thresholds()
        v *= sgn
        if c is not None and v >= c:
            return 2
        if w is not None and v >= w:
            return 1
        return 0

    def _hold_level(self, v: float) -> int:
        """지금 상태를 유지할 수 있는 가장 높은 단계(기준에서 hysteresis만큼 내려오기 전까지 유지)."""
        w, c, sgn = self._thresholds()
        v *= sgn
        cur = LEVELS[self.state]
        lvl = 0
        if cur >= 1 and w is not None and v > w - self.hysteresis:
            lvl = 1
        if cur == 2 and c is not None and v > c - self.hysteresis:
            lvl = 2
        return lvl

    def break_run(self) -> None:
        """좋은 값이 아닌 샘플(bad, stale)이 끼었을 때 올라가는 중이던 연속 횟수를 지운다."""
        self._run = self._run_min = 0

    def update(self, value: float) -> tuple[str, str] | None:
        """새 값을 넣고, 상태가 바뀌면 (이전 상태, 새 상태)를 돌려준다."""
        cur = LEVELS[self.state]
        raw = self._raw_level(value)
        if raw > cur:  # 올라가는 중: 연속 횟수를 센다
            self._run = self._run + 1
            self._run_min = raw if self._run == 1 else min(self._run_min, raw)
            if self._run < self.consecutive:
                return None
            new = self._run_min
            self._run = self._run_min = 0
        else:
            self._run = self._run_min = 0
            hold = self._hold_level(value)
            if hold >= cur:
                return None
            new = hold
        old, self.state = self.state, NAMES[new]
        return old, self.state


def quality_for(value: float, value_range: tuple[float, float]) -> str:
    """범위 밖이면 bad, 아니면 good."""
    lo, hi = value_range
    return "good" if lo <= value <= hi else "bad"
