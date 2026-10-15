"""validate_usd.py 테스트. 임시 USDA 파일을 만들어 규칙별로 통과/실패를 확인한다."""
from __future__ import annotations

from pathlib import Path

import pytest

from validate_usd import main, validate_file

HEADER = """#usda 1.0
(
    defaultPrim = "DC"
    metersPerUnit = 0.01
    upAxis = "Z"
)
"""

GOOD_BODY = """
def Xform "DC"
{
    def Xform "Hall01"
    {
        def Xform "Row01"
        {
            def Xform "Rack_01"
            {
                token dct:assetType = "rack"
                string dct:sensorId = "H01-R01-RK01-TEMP-IN"
                token dct:zone = "cold_aisle"

                def Xform "Server_U01"
                {
                    token dct:assetType = "server"
                }
            }
        }

        def Xform "Cooling"
        {
            def Xform "CRAC_01"
            {
                token dct:assetType = "crac"
                string dct:sensorId = "H01-CRAC01-FAN"
            }
        }

        def Xform "Power"
        {
            def Xform "PDU_01"
            {
                token dct:assetType = "pdu"
                string dct:sensorId = "H01-PDU01-POWER"
            }
        }
    }
}
"""

def write(tmp_path: Path, text: str, name: str = "t.usda") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def rules(tmp_path: Path, text: str, kind: str = "scene") -> set[str]:
    return {f.rule for f in validate_file(write(tmp_path, text), kind) if f.level == "ERROR"}


def test_good_scene_passes(tmp_path):
    assert validate_file(write(tmp_path, HEADER + GOOD_BODY)) == []


def test_wrong_units(tmp_path):
    text = (HEADER + GOOD_BODY).replace("metersPerUnit = 0.01", "metersPerUnit = 1")
    assert "U101" in rules(tmp_path, text)


def test_missing_up_axis(tmp_path):
    text = (HEADER + GOOD_BODY).replace('    upAxis = "Z"\n', "")
    assert "U102" in rules(tmp_path, text)


def test_wrong_up_axis(tmp_path):
    text = (HEADER + GOOD_BODY).replace('upAxis = "Z"', 'upAxis = "Y"')
    assert "U102" in rules(tmp_path, text)


def test_default_prim_must_be_dc(tmp_path):
    text = (HEADER + GOOD_BODY).replace('defaultPrim = "DC"', 'defaultPrim = "World"') + '\ndef Xform "World"\n{\n}\n'
    assert "U103" in rules(tmp_path, text)


def test_bad_hall_name(tmp_path):
    text = (HEADER + GOOD_BODY).replace('"Hall01"', '"HallA"')
    assert "U301" in rules(tmp_path, text)


def test_rack_in_wrong_place(tmp_path):
    text = (HEADER + GOOD_BODY).replace('"Rack_01"', '"Rack_1"')  # 번호가 한 자리
    found = rules(tmp_path, text)
    assert "U202" in found or "U302" in found


def test_equipment_name_without_asset_type(tmp_path):
    text = (HEADER + GOOD_BODY).replace('token dct:assetType = "pdu"\n', "")
    assert "U202" in rules(tmp_path, text)


def test_invalid_asset_type(tmp_path):
    text = (HEADER + GOOD_BODY).replace('"crac"', '"fan"')
    assert "U203" in rules(tmp_path, text)


def test_missing_sensor_id_on_rack(tmp_path):
    text = (HEADER + GOOD_BODY).replace('string dct:sensorId = "H01-R01-RK01-TEMP-IN"', "")
    assert "U401" in rules(tmp_path, text)


def test_bad_sensor_id_format(tmp_path):
    text = (HEADER + GOOD_BODY).replace("H01-R01-RK01-TEMP-IN", "rack1_temp")
    assert "U402" in rules(tmp_path, text)


def test_duplicate_sensor_id(tmp_path):
    text = (HEADER + GOOD_BODY).replace("H01-PDU01-POWER", "H01-CRAC01-FAN")
    assert "U403" in rules(tmp_path, text)


def test_invalid_zone(tmp_path):
    text = (HEADER + GOOD_BODY).replace('"cold_aisle"', '"warm"')
    assert "U501" in rules(tmp_path, text)


def test_asset_kind_requires_asset_type_on_default_prim(tmp_path):
    text = """#usda 1.0
(
    defaultPrim = "Rack"
    metersPerUnit = 0.01
    upAxis = "Z"
)
def Xform "Rack"
{
}
"""
    assert "U201" in rules(tmp_path, text, kind="asset")


def test_asset_kind_passes_without_sensor_id(tmp_path):
    text = """#usda 1.0
(
    defaultPrim = "Rack"
    metersPerUnit = 0.01
    upAxis = "Z"
)
def Xform "Rack"
{
    token dct:assetType = "rack"
}
"""
    assert rules(tmp_path, text, kind="asset") == set()


def test_unopenable_file(tmp_path):
    findings = validate_file(tmp_path / "nope.usda")
    assert any(f.rule == "U000" for f in findings)


def test_cli_exit_codes(tmp_path, capsys):
    good = write(tmp_path, HEADER + GOOD_BODY, "good.usda")
    bad = write(tmp_path, (HEADER + GOOD_BODY).replace("metersPerUnit = 0.01", "metersPerUnit = 1"), "bad.usda")
    assert main([str(good)]) == 0
    assert main([str(bad)]) == 1
    out = capsys.readouterr().out
    assert "통과" in out and "실패" in out
