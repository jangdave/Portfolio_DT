"""build_manifest.py 테스트: 매니페스트가 USD 장면과 어긋나지 않는지 확인한다."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pxr import Usd

from build_manifest import THRESHOLDS, build_manifest, main
from dct_ids import parse_sensor_path, sensor_id_from_path

REPO = Path(__file__).resolve().parents[3]
HALL = REPO / "usd" / "scenes" / "hall01.usda"

HEADER = """#usda 1.0
(
    defaultPrim = "DC"
    metersPerUnit = 0.01
    upAxis = "Z"
)
"""


def scene(tmp_path: Path, body: str) -> Usd.Stage:
    p = tmp_path / "s.usda"
    p.write_text(HEADER + body, encoding="utf-8")
    return Usd.Stage.Open(str(p))


def anchor(metric: str, unit: str, sid: str) -> str:
    return f'''
                def Xform "Sensor_{metric.upper()}"
                {{
                    token dct:assetType = "sensor"
                    token dct:metric = "{metric}"
                    string dct:unit = "{unit}"
                    string dct:sensorId = "{sid}"
                }}'''


SMALL = """
def Xform "DC"
{
    def Xform "Hall01"
    {
        def Xform "Row01"
        {
            def Xform "Rack_01"
            {
                token dct:assetType = "rack"
                def Xform "Anchors"
                {""" + anchor("temp_in", "degC", "H01-RK01-TEMP-IN") + anchor("power", "kW", "H01-RK01-POWER") + """
                }
            }
        }
        def Xform "Cooling"
        {
            def Xform "CRAC_01"
            {
                token dct:assetType = "crac"
                def Xform "Anchors"
                {""" + anchor("fan_speed", "percent", "H01-CR01-FAN-SPEED") + """
                }
            }
        }
    }
}
"""


def test_id_and_topic_from_path():
    p = parse_sensor_path("/DC/Hall01/Row01/Rack_01/Anchors/Sensor_TEMP_IN")
    assert p.sensor_id == "H01-RK01-TEMP-IN"
    assert p.topic == "dct/v1/hall01/rack_01/temp_in"
    assert p.equipment_type == "rack"
    assert sensor_id_from_path("/DC/Hall01/Cooling/CRAC_08/Anchors/Sensor_SUPPLY_TEMP") == "H01-CR08-SUPPLY-TEMP"
    assert sensor_id_from_path("/DC/Hall01/Row01/Rack_01") is None


def test_small_scene_manifest(tmp_path):
    m = build_manifest(scene(tmp_path, SMALL))
    assert m["version"] == 1 and m["hall"] == "hall01"
    assert [s["sensorId"] for s in m["sensors"]] == ["H01-CR01-FAN-SPEED", "H01-RK01-POWER", "H01-RK01-TEMP-IN"]
    fan = next(s for s in m["sensors"] if s["metric"] == "fan_speed")
    assert fan["direction"] == "low" and fan["critical"] == 5 and fan["equipmentType"] == "crac"
    tin = next(s for s in m["sensors"] if s["metric"] == "temp_in")
    assert tin["topic"] == "dct/v1/hall01/rack_01/temp_in" and tin["warn"] == 27 and tin["critical"] == 32
    assert tin["equipmentPath"] == "/DC/Hall01/Row01/Rack_01"


def test_sensor_id_mismatch_stops(tmp_path):
    with pytest.raises(SystemExit):
        build_manifest(scene(tmp_path, SMALL.replace("H01-RK01-POWER", "H01-RK02-POWER")))


def test_duplicate_sensor_id_stops(tmp_path):
    with pytest.raises(SystemExit):
        build_manifest(scene(tmp_path, SMALL.replace("H01-RK01-POWER", "H01-RK01-TEMP-IN")))


def test_wrong_unit_stops(tmp_path):
    # 입구 온도가 degF이면 임계값(degC 기준)이 엉뚱하게 붙는다
    bad = SMALL.replace('string dct:unit = "degC"', 'string dct:unit = "degF"')
    with pytest.raises(SystemExit, match="단위"):
        build_manifest(scene(tmp_path, bad))
    with pytest.raises(SystemExit, match="단위"):
        build_manifest(scene(tmp_path, SMALL.replace('string dct:unit = "kW"', 'string dct:unit = "W"')))


def test_uppercase_metric_stops(tmp_path):
    bad = SMALL.replace('token dct:metric = "temp_in"', 'token dct:metric = "TEMP_IN"')
    with pytest.raises(SystemExit, match="소문자"):
        build_manifest(scene(tmp_path, bad))


def test_anchor_without_sensor_asset_type_stops(tmp_path):
    # 센서 앵커 3개 중 하나의 assetType이 빠지면 조용히 센서가 줄어들지 않고 멈춘다
    bad = SMALL.replace('token dct:assetType = "sensor"', 'token dct:assetType = "rack"', 1)  # 첫 앵커(Sensor_TEMP_IN)의 assetType을 바꾼다
    assert bad != SMALL
    with pytest.raises(SystemExit, match="assetType"):
        build_manifest(scene(tmp_path, bad))


def test_cli_writes_file(tmp_path):
    p = tmp_path / "s.usda"
    p.write_text(HEADER + SMALL, encoding="utf-8")
    out = tmp_path / "out" / "m.json"
    assert main([str(p), str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["hall"] == "hall01"


@pytest.mark.skipif(not HALL.exists(), reason="hall01.usda 없음")
def test_repo_hall_manifest_matches_scene():
    stage = Usd.Stage.Open(str(HALL))
    m = build_manifest(stage)
    n_anchors = sum(1 for p in stage.Traverse() if p.GetAttribute("dct:assetType") and p.GetAttribute("dct:assetType").Get() == "sensor")
    assert len(m["sensors"]) == n_anchors == 204  # 랙 60 x 3 + CRAC 8 x 3
    assert len({s["sensorId"] for s in m["sensors"]}) == len({s["topic"] for s in m["sensors"]}) == 204
    for s in m["sensors"]:
        assert sensor_id_from_path(s["usdPath"]) == s["sensorId"]
        assert (s["equipmentType"], s["metric"]) in THRESHOLDS  # 기준값이 없는 센서가 없어야 알람을 판정할 수 있다
        assert s["topic"].startswith("dct/v1/hall01/")
