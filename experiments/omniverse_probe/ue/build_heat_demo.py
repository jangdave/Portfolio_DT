"""UE 데모: Warp 열 시뮬레이션 볼륨을 '전용 볼륨 머티리얼'로 그린다.

내장 뷰어(build_volume_demo.py)는 값을 흑백 농도로만 보여 줘서 선명하지 않았다. 이 스크립트는
- 온도(정규화한 값)를 알람 기준에 맞춘 색(파랑 → 노랑 → 빨강 → 흰색)으로 바꾸고
- 불투명도(extinction)와 발광을 값으로 조절하는 Volume 도메인 머티리얼을 만들고
- HeterogeneousVolume 액터로 8프레임 애니메이션을 반복 재생하는 레벨을 만든다.
프로젝트 시작 스크립트로 실행한다. 환경 변수: DCT_VDB_FILES(번호 붙은 .vdb의 첫 파일), DCT_UE_RESULT

볼륨 값: value = clip((T - 24) / (54 - 24), 0, 1). 알람 기준은 같은 식으로 바꾼 값이다.
  주의 27도 -> 0.10, 위험 32도 -> 0.267
"""
import json
import math
import os
import traceback

import unreal

PKG = "/Game/HeatDemo"
MAP = f"{PKG}/HeatDemo"
T_MIN, T_MAX, T_WARN, T_CRIT = 24.0, 54.0, 27.0, 32.0
WARN_N = (T_WARN - T_MIN) / (T_MAX - T_MIN)
CRIT_N = (T_CRIT - T_MIN) / (T_MAX - T_MIN)
result_path = os.environ.get("DCT_UE_RESULT", "D:/ue_probe/heat_result.json")
res = {"steps": {}}
state = {"tick": 0, "done": False}
refs = {}
mel = unreal.MaterialEditingLibrary


def log(name, ok, detail=None):
    res["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[ue_heat] {name}: {'OK' if ok else 'FAIL'} {detail if detail is not None else ''}", flush=True)


def save_result():
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)


# ---- 머티리얼 노드 도우미 ----
def new(mat, cls, x, y):
    return mel.create_material_expression(mat, cls, x, y)


def const(mat, v, x, y):
    n = new(mat, unreal.MaterialExpressionConstant, x, y)
    n.set_editor_property("r", float(v))
    return n


def color(mat, rgb, x, y):
    n = new(mat, unreal.MaterialExpressionConstant3Vector, x, y)
    n.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    return n


def param(mat, name, default, x, y):
    n = new(mat, unreal.MaterialExpressionScalarParameter, x, y)
    n.set_editor_property("parameter_name", name)
    n.set_editor_property("default_value", float(default))
    return n


def remap01(mat, src, lo, hi, x, y):
    """(src - lo) / (hi - lo)를 0~1로 자른다."""
    sub = new(mat, unreal.MaterialExpressionSubtract, x, y)
    mel.connect_material_expressions(src, "", sub, "A")
    sub.set_editor_property("const_b", float(lo))
    div = new(mat, unreal.MaterialExpressionDivide, x + 160, y)
    mel.connect_material_expressions(sub, "", div, "A")
    div.set_editor_property("const_b", float(max(hi - lo, 1e-6)))
    clamp = new(mat, unreal.MaterialExpressionClamp, x + 320, y)
    mel.connect_material_expressions(div, "", clamp, "")
    clamp.set_editor_property("min_default", 0.0)
    clamp.set_editor_property("max_default", 1.0)
    return clamp


def lerp(mat, a, b, alpha, x, y):
    n = new(mat, unreal.MaterialExpressionLinearInterpolate, x, y)
    mel.connect_material_expressions(a, "", n, "A")
    mel.connect_material_expressions(b, "", n, "B")
    mel.connect_material_expressions(alpha, "", n, "Alpha")
    return n


def mul(mat, a, b, x, y):
    n = new(mat, unreal.MaterialExpressionMultiply, x, y)
    mel.connect_material_expressions(a, "", n, "A")
    mel.connect_material_expressions(b, "", n, "B")
    return n


def build_material(svt):
    atools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = atools.create_asset("M_TempVolume", PKG, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    try:
        mat.set_editor_property("used_with_heterogeneous_volumes", True)
    except Exception as exc:  # noqa: BLE001
        res["flag_error"] = str(exc)

    # 볼륨 샘플 -> 첫 속성의 R 채널(정규화한 온도 v)
    obj = new(mat, unreal.MaterialExpressionSparseVolumeTextureObjectParameter, -1500, -300)
    obj.set_editor_property("parameter_name", "TempSVT")
    obj.set_editor_property("sparse_volume_texture", svt)
    smp = new(mat, unreal.MaterialExpressionSparseVolumeTextureSample, -1200, -300)
    mel.connect_material_expressions(obj, "", smp, "TextureObject")
    mask = new(mat, unreal.MaterialExpressionComponentMask, -950, -300)
    for ch, on in (("r", True), ("g", False), ("b", False), ("a", False)):
        mask.set_editor_property(ch, on)
    ok = mel.connect_material_expressions(smp, "Attributes A", mask, "")
    res["sample_connected"] = bool(ok)
    v = mask

    # 알람 기준에 맞춘 색 사다리: 파랑 -> 노랑(주의) -> 빨강(위험) -> 흰색
    c_cool, c_warn = color(mat, (0.03, 0.2, 1.0), -700, -700), color(mat, (1.0, 0.85, 0.05), -700, -600)
    c_crit, c_hot = color(mat, (1.0, 0.12, 0.02), -700, -500), color(mat, (1.0, 0.92, 0.8), -700, -400)
    a1 = remap01(mat, v, 0.0, WARN_N, -700, -100)
    a2 = remap01(mat, v, WARN_N, CRIT_N, -700, 100)
    a3 = remap01(mat, v, CRIT_N, 1.0, -700, 300)
    l1 = lerp(mat, c_cool, c_warn, a1, -200, -600)
    l2 = lerp(mat, l1, c_crit, a2, 0, -500)
    ramp = lerp(mat, l2, c_hot, a3, 200, -400)

    # 불투명도(extinction) = v^Contrast * DensityScale, 발광 = 색 * v * EmissiveGain
    contrast = param(mat, "Contrast", 1.2, 0, 700)
    density = param(mat, "DensityScale", 0.004, 0, 800)  # 홀 폭 600cm에서 값 0.5일 때 광학 두께가 약 1.2가 되도록
    gain = param(mat, "EmissiveGain", 2.0, 0, 900)
    powv = new(mat, unreal.MaterialExpressionPower, 250, 700)
    mel.connect_material_expressions(v, "", powv, "Base")
    mel.connect_material_expressions(contrast, "", powv, "Exp")
    extinction = mul(mat, powv, density, 500, 700)
    glow = mul(mat, v, gain, 500, 900)
    emissive = mul(mat, ramp, glow, 750, 800)

    mel.connect_material_property(ramp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(extinction, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)

    mi = atools.create_asset("MI_TempVolume", PKG, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", mat)
    mel.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mat, mi


def setup():
    level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # 1) 볼륨 가져오기
    seq_first = os.environ.get("DCT_VDB_FILES", "").split(";")[0]
    task = unreal.AssetImportTask()
    task.filename = seq_first
    task.destination_path = PKG
    task.destination_name = "TempN"
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objs = task.get_objects()
    svt = objs[0] if objs else None
    size = (svt.get_size_x(), svt.get_size_y(), svt.get_size_z()) if svt is not None else None
    log("import_svt", svt is not None, {"class": svt.get_class().get_name() if svt else None, "size": size, "frames": svt.get_num_frames() if svt is not None else None})

    # 2) 머티리얼
    mat, mi = build_material(svt)
    log("material", mat is not None, {"sample_connected": res.get("sample_connected"), "warn_n": round(WARN_N, 3), "crit_n": round(CRIT_N, 3)})

    # 3) 레벨
    log("new_level", bool(level_sub.new_level(MAP)), MAP)
    hv = actor_sub.spawn_actor_from_class(unreal.HeterogeneousVolume, unreal.Vector(0, 0, 0))
    hv.set_actor_label("HallTemperature")
    comp = hv.get_editor_property("heterogeneous_volume_component")
    comp.set_material(0, mi)
    sx, sy, sz = size if size else (80, 60, 35)
    props = {}
    for name, value in (("volume_resolution", unreal.IntVector(int(sx), int(sy), int(sz))), ("playing", True), ("looping", True), ("frame_rate", 2.0), ("start_frame", 0.0), ("end_frame", 7.0)):
        try:
            comp.set_editor_property(name, value)
            props[name] = "OK"
        except Exception as exc:  # noqa: BLE001
            props[name] = f"실패: {str(exc)[:80]}"
    # HeterogeneousVolume의 영역은 SVT 크기가 아니라 액터 스케일이 정하는 상자다(기본 1 x 1 x 1 단위 상자가 중심 기준).
    # 그래서 홀 크기(가로 800, 세로 600, 높이 350 cm)로 직접 키우고, 홀 중심에 놓는다.
    hall_cm = (800.0, 600.0, 350.0)
    hv.set_actor_scale3d(unreal.Vector(*hall_cm))
    hv.set_actor_location(unreal.Vector(hall_cm[0] / 2, hall_cm[1] / 2, hall_cm[2] / 2), False, False)
    log("heterogeneous_volume", True, {"box_cm": hall_cm, "props": props})

    floor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(400, 300, -2))
    floor.set_actor_label("Floor")
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(10, 8, 1))
    sun = actor_sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 600))
    sun.set_actor_label("Sun")
    sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-45, yaw=30), False)
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 3.0)
    actor_sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 700)).set_actor_label("Sky")
    cam = actor_sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(1250, -650, 520))
    cam.set_actor_label("Cam_Hall")
    cam.set_actor_rotation(unreal.Rotator(roll=0, pitch=-19, yaw=132), False)

    log("save_level", bool(level_sub.save_current_level()), MAP)
    unreal.EditorAssetLibrary.save_directory(PKG, only_if_is_dirty=False)


def on_tick(delta):
    state["tick"] += 1
    try:
        if state["tick"] == 30:
            setup()
        if state["tick"] >= 70 and not state["done"]:
            state["done"] = True
            save_result()
            unreal.unregister_slate_post_tick_callback(refs["h"])
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
    except Exception:  # noqa: BLE001
        res["tick_error"] = traceback.format_exc()
        print(res["tick_error"], flush=True)
        state["done"] = True
        save_result()
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


refs["h"] = unreal.register_slate_post_tick_callback(on_tick)
print("[ue_heat] 시작 스크립트 등록 완료", flush=True)
