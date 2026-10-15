"""알람 판정 규칙 시험. alarm_vectors.json은 게이트웨이(Node)도 같이 쓴다."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dct_sensors.alarms import AlarmState, quality_for

CASES = json.loads((Path(__file__).parent / "alarm_vectors.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_vectors(case):
    a = AlarmState(case["warn"], case["critical"], case["direction"], case["hysteresis"], case["consecutive"])
    got = []
    for i, v in enumerate(case["values"]):
        tr = a.update(v)
        if tr:
            got.append({"index": i, "from": tr[0], "to": tr[1]})
    assert got == case["transitions"]


def test_quality_out_of_range_is_bad():
    assert quality_for(24.0, (10, 45)) == "good"
    assert quality_for(60.0, (10, 45)) == "bad"
    assert quality_for(-1.0, (0, 100)) == "bad"
