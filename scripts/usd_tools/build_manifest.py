"""USD 장면에서 센서 매니페스트(JSON)를 만든다. 센서 값을 해석하는 데 필요한 정보를 한 파일에 모은다.

생성기, 게이트웨이, Unreal이 모두 이 파일을 기준으로 삼는다(ADR-005, 11 데이터 규격 3장). Unreal은 USD 속성을 읽지 않아도 된다.

사용 (scripts/usd_tools 폴더에서):
    uv run --python 3.13 python build_manifest.py ../../usd/scenes/hall01.usda ../../sim/out/sensor_manifest.json

- 센서 ID와 MQTT 주소는 USD 경로에서 계산한다(`dct_ids.py` 한 곳). 장면의 `dct:sensorId`가 경로에서 계산한 값과 다르면 오류로 멈춘다.
- 범위와 알람 기준은 아래 표(11 데이터 규격 3장의 기본 기준값)다. **데모용으로 정한 값이며 실제 시설 기준이 아니다.**
- 결과는 `sim/out/`에 쓰고 Git에는 올리지 않는다. 생성 스크립트로 다시 만든다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pxr import Usd

from dct_ids import parse_sensor_path

# (장비 종류, 측정 종류) -> 범위, 주의, 위험, 방향. 방향이 "low"이면 값이 낮을수록 위험(기본은 "high")
THRESHOLDS: dict[tuple[str, str], dict] = {
    ("rack", "temp_in"): {"range": [10, 45], "warn": 27, "critical": 32},
    ("rack", "temp_out"): {"range": [15, 60], "warn": 40, "critical": 50},
    ("rack", "power"): {"range": [0, 15], "warn": 10, "critical": 13},
    ("crac", "supply_temp"): {"range": [10, 30], "warn": 22, "critical": 26},
    ("crac", "return_temp"): {"range": [15, 50], "warn": 35, "critical": 42},
    ("crac", "fan_speed"): {"range": [0, 100], "warn": 20, "critical": 5, "direction": "low"},
    ("pdu", "power"): {"range": [0, 60], "warn": 45, "critical": 55},
    ("pdu", "load"): {"range": [0, 100], "warn": 80, "critical": 90},
}


# 기준값이 정해진 센서는 단위도 정해져 있다. 다르면 임계값(도, kW 기준)이 엉뚱하게 붙으므로 멈춘다.
EXPECTED_UNITS = {
    ("rack", "temp_in"): "degC", ("rack", "temp_out"): "degC", ("rack", "power"): "kW",
    ("crac", "supply_temp"): "degC", ("crac", "return_temp"): "degC", ("crac", "fan_speed"): "percent",
    ("pdu", "power"): "kW", ("pdu", "load"): "percent",
}


def build_manifest(stage: Usd.Stage) -> dict:
    sensors = []
    seen_ids: dict[str, str] = {}
    seen_topics: dict[str, str] = {}
    halls: set[str] = set()
    for prim in stage.Traverse():
        at = prim.GetAttribute("dct:assetType")
        path = str(prim.GetPath())
        if (not at or at.Get() != "sensor"):
            if parse_sensor_path(path) is not None:  # Anchors/Sensor_* 이름인데 assetType이 sensor가 아니면 조용히 빠지지 않게 멈춘다
                raise SystemExit(f"센서 앵커 이름인데 dct:assetType이 sensor가 아니다: {path}")
            continue
        sp = parse_sensor_path(path)
        if sp is None:
            raise SystemExit(f"센서 앵커 경로가 규칙과 맞지 않는다: {path}")
        declared = prim.GetAttribute("dct:sensorId").Get() if prim.GetAttribute("dct:sensorId") else None
        if declared != sp.sensor_id:
            raise SystemExit(f"센서 ID가 경로에서 만든 값과 다르다: {path} 장면 '{declared}' / 경로 '{sp.sensor_id}'")
        metric = prim.GetAttribute("dct:metric").Get()
        unit = prim.GetAttribute("dct:unit").Get()
        if not metric or not unit or metric.upper() != sp.metric_upper:
            raise SystemExit(f"metric/unit이 없거나 앵커 이름과 다르다: {path}")
        if metric != metric.lower():  # 기준값 조회와 생성기의 비교가 소문자 기준이다
            raise SystemExit(f"dct:metric은 소문자여야 한다: '{metric}' ({path})")
        expected_unit = EXPECTED_UNITS.get((sp.equipment_type, metric))
        if expected_unit is not None and unit != expected_unit:
            raise SystemExit(f"단위가 기준과 다르다: {path} '{unit}' (기대 '{expected_unit}')")
        if sp.sensor_id in seen_ids:
            raise SystemExit(f"센서 ID가 중복되었다: {sp.sensor_id} ({seen_ids[sp.sensor_id]}, {path})")
        if sp.topic in seen_topics:
            raise SystemExit(f"MQTT 주소가 중복되었다: {sp.topic} ({seen_topics[sp.topic]}, {path})")
        seen_ids[sp.sensor_id], seen_topics[sp.topic] = path, path
        halls.add(f"hall{sp.hall_no}")
        item = {
            "sensorId": sp.sensor_id,
            "topic": sp.topic,
            "usdPath": path,
            "equipmentPath": path.rsplit("/Anchors/", 1)[0],
            "equipmentType": sp.equipment_type,
            "metric": metric,
            "unit": unit,
        }
        th = THRESHOLDS.get((sp.equipment_type, metric))
        if th is None:
            print(f"[경고] 기준값이 없는 센서(알람을 판정하지 않음): {sp.equipment_type}/{metric} {sp.sensor_id}", file=sys.stderr)
        else:
            item.update(th)
        sensors.append(item)
    if len(halls) != 1:
        raise SystemExit(f"홀이 하나가 아니다: {sorted(halls)}")
    sensors.sort(key=lambda s: s["sensorId"])
    return {"version": 1, "hall": halls.pop(), "sensors": sensors}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="USD 장면에서 센서 매니페스트 만들기")
    ap.add_argument("scene", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stage = Usd.Stage.Open(str(args.scene))
    if stage is None:
        raise SystemExit(f"장면을 열 수 없다: {args.scene}")
    manifest = build_manifest(stage)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    kinds: dict[str, int] = {}
    for s in manifest["sensors"]:
        k = f"{s['equipmentType']}/{s['metric']}"
        kinds[k] = kinds.get(k, 0) + 1
    print(f"센서 {len(manifest['sensors'])}개 ({manifest['hall']}) -> {args.out}")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
