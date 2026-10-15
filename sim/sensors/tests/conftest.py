"""시험용 작은 홀 매니페스트: 줄 2개(랙 3기씩), CRAC 4기. 배치 규칙(줄 수 // 2 + 1 = 한쪽 CRAC 수)을 지킨다."""
from __future__ import annotations

import json

import pytest

THRESH = {
    ("rack", "temp_in"): ([10, 45], 27, 32, "high", "degC"),
    ("rack", "temp_out"): ([15, 60], 40, 50, "high", "degC"),
    ("rack", "power"): ([0, 15], 10, 13, "high", "kW"),
    ("crac", "supply_temp"): ([10, 30], 22, 26, "high", "degC"),
    ("crac", "return_temp"): ([15, 50], 35, 42, "high", "degC"),
    ("crac", "fan_speed"): ([0, 100], 20, 5, "low", "percent"),
}


def make_manifest_data(n_rows: int = 2, racks_per_row: int = 3) -> dict:
    per_side = n_rows // 2 + 1
    sensors = []

    def add(eq_path, eq_name, eq_type, metric, num):
        rng, warn, crit, direction, unit = THRESH[(eq_type, metric)]
        code = {"rack": "RK", "crac": "CR"}[eq_type]
        item = {
            "sensorId": f"H01-{code}{num:02d}-{metric.upper().replace('_', '-')}",
            "topic": f"dct/v1/hall01/{eq_name}/{metric}",
            "usdPath": f"{eq_path}/Anchors/Sensor_{metric.upper()}",
            "equipmentPath": eq_path, "equipmentType": eq_type, "metric": metric, "unit": unit,
            "range": rng, "warn": warn, "critical": crit,
        }
        if direction == "low":
            item["direction"] = "low"
        sensors.append(item)

    n = 0
    for row in range(1, n_rows + 1):
        for _ in range(racks_per_row):
            n += 1
            for metric in ("temp_in", "temp_out", "power"):
                add(f"/DC/Hall01/Row{row:02d}/Rack_{n:02d}", f"rack_{n:02d}", "rack", metric, n)
    for c in range(1, 2 * per_side + 1):
        for metric in ("supply_temp", "return_temp", "fan_speed"):
            add(f"/DC/Hall01/Cooling/CRAC_{c:02d}", f"crac_{c:02d}", "crac", metric, c)
    return {"version": 1, "hall": "hall01", "sensors": sensors}


@pytest.fixture
def manifest():
    from dct_sensors.manifest import Manifest

    return Manifest(make_manifest_data())


@pytest.fixture
def manifest_file(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(make_manifest_data()), encoding="utf-8")
    return p
