"""서버 랙 블록아웃(대략 모델)을 만든다. 직접 모델링을 시작하는 기준점이다.

실행 (저장소 루트에서):
    blender -b --factory-startup --python blender/scripts/make_rack_blockout.py -- blender/rack_blockout.blend

- 단위: Blender 1 단위 = 1 cm (장면 단위 cm)
- 크기: 가로 60 x 깊이 100 x 높이 200 cm. 서버 1U = 4.445 cm (19인치 랙의 공개 표준 높이)
- 실제 제품을 따라 만들지 않은 가상 장비다.
"""
from __future__ import annotations

import sys

import bpy

U = 4.445  # 서버 1U 높이(cm)
RACK_W, RACK_D, RACK_H = 60.0, 100.0, 200.0
BASE_H, TOP_H, POST = 5.0, 3.0, 4.0
SERVER_W, SERVER_D = 48.26, 70.0  # 19인치 폭, 깊이는 가상 값
FIRST_U_Z = BASE_H + 4.0  # 첫 번째 U의 바닥 높이

# (시작 U, 높이 U): 앞쪽 일부만 채운 예시 구성
SERVERS = [(1, 1), (2, 1), (3, 2), (5, 2), (8, 1), (9, 1), (10, 4), (20, 2), (22, 2), (30, 1)]


def setup_units() -> None:
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.01
    s.unit_settings.length_unit = "CENTIMETERS"


def make_material(name: str, rgba: tuple[float, float, float, float], metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def box(name: str, size, center, mat, parent=None):
    """size/center 단위는 cm. 가로, 깊이, 높이 순서."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name + "_mesh"
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # 스케일을 모양에 적용
    ob.data.materials.append(mat)
    if parent is not None:
        _attach(ob, parent)
    return ob


def _attach(child, parent) -> None:
    """부모에 붙이되 월드 위치는 그대로 유지한다. (역행렬을 넣지 않으면 부모 위치가 한 번 더 더해진다.)"""
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def empty(name: str, location, parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        _attach(ob, parent)
    return ob


def build() -> None:
    setup_units()
    m_frame = make_material("M_RackFrame", (0.08, 0.08, 0.09, 1), 0.8, 0.45)
    m_body = make_material("M_ServerBody", (0.02, 0.02, 0.025, 1), 0.3, 0.6)
    m_front = make_material("M_ServerFront", (0.35, 0.37, 0.4, 1), 0.2, 0.5)  # 열 표시용 머티리얼 칸

    rack = empty("Rack", (0, 0, 0))
    rack["assetType"] = "rack"

    # 프레임: 바닥판, 윗판, 기둥 4개
    box("Frame_Base", (RACK_W, RACK_D, BASE_H), (0, 0, BASE_H / 2), m_frame, rack)
    box("Frame_Top", (RACK_W, RACK_D, TOP_H), (0, 0, RACK_H - TOP_H / 2), m_frame, rack)
    post_h = RACK_H - BASE_H - TOP_H
    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)], start=1):
        box(
            f"Frame_Post_{i:02d}",
            (POST, POST, post_h),
            (sx * (RACK_W / 2 - POST / 2), sy * (RACK_D / 2 - POST / 2), BASE_H + post_h / 2),
            m_frame,
            rack,
        )

    # 서버: 앞(-Y)쪽에 맞춰 배치. 이름은 Server_U{시작 U 두 자리}
    front_y = -RACK_D / 2 + POST + 2.0
    for start_u, height_u in SERVERS:
        h = height_u * U - 0.4  # 서버 사이에 약간의 틈
        z = FIRST_U_Z + (start_u - 1) * U + h / 2
        body = box(f"Server_U{start_u:02d}", (SERVER_W, SERVER_D, h), (0, front_y + SERVER_D / 2, z), m_body, rack)
        body["assetType"] = "server"
        # 앞면 패널: 열 표시 색을 입힐 부분
        box(
            f"Server_U{start_u:02d}_Face",
            (SERVER_W, 1.0, h),
            (0, front_y - 0.5, z),
            m_front,
            body,
        )

    # 센서 위치 표시용 빈 오브젝트
    anchors = empty("Anchors", (0, 0, 0), rack)
    # (측정 종류, 단위, y 위치): 09 규격 4장의 랙 기본 센서 3개. 전력은 랙 위쪽 한가운데에 둔다.
    for metric, unit, y, z in (
        ("temp_in", "degC", -RACK_D / 2 - 5.0, RACK_H * 0.6),
        ("temp_out", "degC", RACK_D / 2 + 5.0, RACK_H * 0.6),
        ("power", "kW", 0.0, RACK_H * 0.9),
    ):
        a = empty(f"Sensor_{metric.upper()}", (0, y, z), anchors)
        a["assetType"] = "sensor"
        a["metric"] = metric
        a["unit"] = unit


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "rack_blockout.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("저장:", out)
