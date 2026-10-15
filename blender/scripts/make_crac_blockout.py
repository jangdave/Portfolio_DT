"""CRAC(룸 에어컨) 블록아웃(대략 모델)을 만든다.

실행 (저장소 루트에서):
    blender -b --factory-startup --python blender/scripts/make_crac_blockout.py -- blender/crac_blockout.blend

- 단위: Blender 1 단위 = 1 cm (장면 단위 cm)
- 크기: 가로 90 x 깊이 100 x 높이 220 cm. 실제 제품을 따라 만들지 않은 가상 장비다.
- 앞쪽(-Y)이 뜨거운 공기를 빨아들이는 회수면이다. 찬 공기는 아래(바닥 쪽)로 내보낸다고 본다.
- 원점은 바닥 면의 중앙이다.
"""
from __future__ import annotations

import sys

import bpy

sys.path.insert(0, __file__.rsplit("make_crac_blockout.py", 1)[0])
from make_rack_blockout import box, empty, make_material, setup_units  # noqa: E402  (랙 스크립트의 도우미를 그대로 쓴다)

CRAC_W, CRAC_D, CRAC_H = 90.0, 100.0, 220.0
BASE_H = 10.0
FACE_T = 2.0


def build() -> None:
    setup_units()
    m_body = make_material("M_CracBody", (0.55, 0.57, 0.6, 1), 0.4, 0.5)
    m_return = make_material("M_CracReturn", (0.05, 0.05, 0.06, 1), 0.2, 0.7)  # 회수면(뜨거운 공기 흡입구)
    m_top = make_material("M_CracTop", (0.3, 0.32, 0.35, 1), 0.5, 0.5)

    crac = empty("CRAC", (0, 0, 0))
    crac["assetType"] = "crac"

    box("Body_Base", (CRAC_W, CRAC_D, BASE_H), (0, 0, BASE_H / 2), m_top, crac)
    box("Body_Main", (CRAC_W, CRAC_D - FACE_T, CRAC_H - BASE_H), (0, FACE_T / 2, BASE_H + (CRAC_H - BASE_H) / 2), m_body, crac)
    box("Return_Grille", (CRAC_W - 10.0, FACE_T, CRAC_H - BASE_H - 30.0), (0, -CRAC_D / 2 + FACE_T / 2, BASE_H + 10.0 + (CRAC_H - BASE_H - 30.0) / 2), m_return, crac)

    anchors = empty("Anchors", (0, 0, 0), crac)
    # 09 규격 4장의 CRAC 기본 센서 3개
    for metric, unit, y, z in (
        ("supply_temp", "degC", CRAC_D / 2 + 5.0, 30.0),
        ("return_temp", "degC", -CRAC_D / 2 - 5.0, CRAC_H * 0.6),
        ("fan_speed", "percent", 0.0, CRAC_H + 5.0),
    ):
        a = empty(f"Sensor_{metric.upper()}", (0, y, z), anchors)
        a["assetType"] = "sensor"
        a["metric"] = metric
        a["unit"] = unit


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "crac_blockout.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("저장:", out)
