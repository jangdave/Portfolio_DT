"""시나리오 4종 (11 데이터 규격 6.1장).

시나리오는 시간에 따른 **제어 변화(이벤트)** 의 목록이다. 센서 값은 모델(L0, L1)이 제어에서 계산한다.
- `crac_fan`: CRAC 팬 비율(0~1)을 바꾼다. 대상은 `crac_02`처럼 이름.
- `rack_power_scale`: 랙 전력을 배수로 바꾼다. 대상은 `row:02`(줄 전체) 또는 `rack_21`.

현재 홀에는 PDU가 없어서 `power_spike`는 문서의 "PDU_03 담당 랙" 대신 **한 줄(Row02)의 랙**을 대상으로 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    t: float            # 시작 후 초
    kind: str           # "crac_fan" | "rack_power_scale"
    target: str         # "crac_02" | "row:02" | "rack_21"
    value: float


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    events: tuple[Event, ...] = field(default_factory=tuple)


SCENARIOS: dict[str, Scenario] = {s.name: s for s in (
    Scenario("normal", "전력이 완만하게 오르내리고 온도는 정상 범위. 알람 없음"),
    Scenario("cooling_failure", "시작 후 60초에 CRAC_02 팬이 멈춘다. 가까운 랙 입구 온도가 올라 주의, 위험 알람",
             (Event(60, "crac_fan", "crac_02", 0.0),)),
    Scenario("power_spike", "시작 후 30초에 Row02 랙의 전력이 40% 늘어난다. 전력과 온도 상승",
             (Event(30, "rack_power_scale", "row:02", 1.4),)),
    Scenario("fan_fault", "CRAC_01 팬 속도가 15%로 떨어진다(주의 기준 20% 이하). 팬 속도 알람, 일부 랙 온도가 완만하게 상승",
             (Event(30, "crac_fan", "crac_01", 0.15),)),
)}


def get(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError:
        raise SystemExit(f"알 수 없는 시나리오: {name} (있는 것: {', '.join(SCENARIOS)})") from None
