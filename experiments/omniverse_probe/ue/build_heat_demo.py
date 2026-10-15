"""UE 데모: Warp 열 시뮬레이션 볼륨을 '전용 볼륨 머티리얼'로 그리고, 실제 랙과 CRAC 위치에 상자를 함께 놓아 축 방향을 비교한다.

레벨 3개를 만든다. 데이터는 같고 축 방향만 다르다.
  HeatDemo_N  : 원본 그대로
  HeatDemo_FX : X축을 뒤집은 데이터
  HeatDemo_FY : Y축을 뒤집은 데이터
UE의 SVT 임포터는 VDB 변환의 부호를 무시하고 격자 인덱스를 그대로 쓴다는 실무 기록이 있어, 어느 쪽이 실제 장비 위치와 맞는지 눈으로 확인한다.
맞는 기준: CRAC_02(동쪽, 오른쪽 끝)가 고장이라 **동쪽에서 열이 시작**되고, 서쪽(CRAC_01 쪽)은 차갑게 남아야 한다.

머티리얼의 SVT 파라미터 이름은 엔진 기본 Sparse Volume 머티리얼과 같은 "SparseVolumeTexture"로 통일한다.
프로젝트 시작 스크립트로 실행한다. 환경 변수:
  DCT_VDB_FILES : 번호 붙은 .vdb 시퀀스의 첫 파일 3개를 ';'로 구분 (원본; X뒤집기; Y뒤집기)
  DCT_LAYOUT    : 랙/CRAC 위치 JSON,  DCT_UE_RESULT : 결과 JSON

볼륨 값: value = clip((T - 24) / (54 - 24), 0, 1). 알람 기준은 같은 식으로 바꾼 값이다. 주의 27도 -> 0.10, 위험 32도 -> 0.267
"""
import json
import os
import traceback

import unreal

PKG = "/Game/HeatDemo"
SVT_PARAM = "SparseVolumeTexture"  # 엔진 기본 Sparse Volume 머티리얼과 같은 파라미터 이름
T_MIN, T_MAX, T_WARN, T_CRIT = 24.0, 54.0, 27.0, 32.0
WARN_N = (T_WARN - T_MIN) / (T_MAX - T_MIN)
CRIT_N = (T_CRIT - T_MIN) / (T_MAX - T_MIN)
HALL_CM = (800.0, 600.0, 350.0)
VARIANTS = [("N", "TempN"), ("FX", "TempFX"), ("FY", "TempFY")]
result_path = os.environ.get("DCT_UE_RESULT", "D:/ue_probe/heat_result.json")
layout_path = os.environ.get("DCT_LAYOUT", "D:/Test/experiments/omniverse_probe/out/layout.json")
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


def build_material(tag, svt):
    atools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = atools.create_asset(f"M_TempVolume_{tag}", PKG, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    try:
        mat.set_editor_property("used_with_heterogeneous_volumes", True)
    except Exception as exc:  # noqa: BLE001
        res["flag_error"] = str(exc)

    obj = new(mat, unreal.MaterialExpressionSparseVolumeTextureObjectParameter, -1500, -300)
    obj.set_editor_property("parameter_name", SVT_PARAM)
    obj.set_editor_property("sparse_volume_texture", svt)
    smp = new(mat, unreal.MaterialExpressionSparseVolumeTextureSample, -1200, -300)
    mel.connect_material_expressions(obj, "", smp, "TextureObject")
    mask = new(mat, unreal.MaterialExpressionComponentMask, -950, -300)
    for ch, on in (("r", True), ("g", False), ("b", False), ("a", False)):
        mask.set_editor_property(ch, on)
    res.setdefault("sample_connected", {})[tag] = bool(mel.connect_material_expressions(smp, "Attributes A", mask, ""))
    v = mask

    c_cool, c_warn = color(mat, (0.03, 0.2, 1.0), -700, -700), color(mat, (1.0, 0.85, 0.05), -700, -600)
    c_crit, c_hot = color(mat, (1.0, 0.12, 0.02), -700, -500), color(mat, (1.0, 0.92, 0.8), -700, -400)
    a1 = remap01(mat, v, 0.0, WARN_N, -700, -100)
    a2 = remap01(mat, v, WARN_N, CRIT_N, -700, 100)
    a3 = remap01(mat, v, CRIT_N, 1.0, -700, 300)
    ramp = lerp(mat, lerp(mat, lerp(mat, c_cool, c_warn, a1, -200, -600), c_crit, a2, 0, -500), c_hot, a3, 200, -400)

    contrast = param(mat, "Contrast", 1.2, 0, 700)
    density = param(mat, "DensityScale", 0.004, 0, 800)  # 홀 폭 600cm에서 값 0.5일 때 광학 두께가 약 1.2
    gain = param(mat, "EmissiveGain", 2.0, 0, 900)
    powv = new(mat, unreal.MaterialExpressionPower, 250, 700)
    mel.connect_material_expressions(v, "", powv, "Base")
    mel.connect_material_expressions(contrast, "", powv, "Exp")
    extinction = mul(mat, powv, density, 500, 700)
    emissive = mul(mat, ramp, mul(mat, v, gain, 500, 900), 750, 800)

    mel.connect_material_property(ramp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(extinction, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)

    mi = atools.create_asset(f"MI_TempVolume_{tag}", PKG, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", mat)
    mel.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


def import_svt(first_file, name):
    task = unreal.AssetImportTask()
    task.filename = first_file
    task.destination_path = PKG
    task.destination_name = name
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objs = task.get_objects()
    return objs[0] if objs else None


def spawn_box(actor_sub, label, bmin, bmax):
    """cm 단위 최소/최대 좌표로 기본 큐브(100cm)를 늘려 놓는다."""
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")
    size = [bmax[i] - bmin[i] for i in range(3)]
    center = [(bmax[i] + bmin[i]) / 2 for i in range(3)]
    a = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*center))
    a.set_actor_label(label)
    a.static_mesh_component.set_static_mesh(cube)
    a.set_actor_scale3d(unreal.Vector(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
    return a


def build_level(tag, mi, svt, layout):
    level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    path = f"{PKG}/HeatDemo_{tag}"
    ok = level_sub.new_level(path)
    size = (svt.get_size_x(), svt.get_size_y(), svt.get_size_z())

    # 볼륨: 영역은 액터 스케일이 정하는 상자(중심 기준, 기본 1 x 1 x 1)이므로 홀 크기로 키우고 홀 중심에 놓는다.
    hv = actor_sub.spawn_actor_from_class(unreal.HeterogeneousVolume, unreal.Vector(*[c / 2 for c in HALL_CM]))
    hv.set_actor_label(f"HallTemperature_{tag}")
    comp = hv.get_editor_property("heterogeneous_volume_component")
    comp.set_material(0, mi)
    props = {}
    for name, value in (("volume_resolution", unreal.IntVector(int(size[0]), int(size[1]), int(size[2]))), ("playing", True), ("looping", True), ("frame_rate", 2.0), ("start_frame", 0.0), ("end_frame", 7.0)):
        try:
            comp.set_editor_property(name, value)
        except Exception as exc:  # noqa: BLE001
            props[name] = f"실패: {str(exc)[:60]}"
    hv.set_actor_scale3d(unreal.Vector(*HALL_CM))

    # 기준 장비: 실제 위치에 놓은 랙(10기)과 CRAC(2기)
    for r in layout["racks"]:
        spawn_box(actor_sub, f"{r['name']}", r["min"], r["max"])
    for c in layout["cracs"]:
        spawn_box(actor_sub, f"{c['name']}{' (고장)' if c['name'].endswith('02') else ''}", c["min"], c["max"])

    floor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(400, 300, -2))
    floor.set_actor_label("Floor")
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(10, 8, 1))
    sun = actor_sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 600))
    sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-45, yaw=30), False)
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 3.0)
    actor_sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 700))
    cam = actor_sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(1250, -650, 520))
    cam.set_actor_label("Cam_Hall")
    cam.set_actor_rotation(unreal.Rotator(roll=0, pitch=-19, yaw=132), False)
    saved = level_sub.save_current_level()
    log(f"level_{tag}", bool(ok) and bool(saved), {"svt_size": size, "prop_failures": props})


def setup():
    files = os.environ.get("DCT_VDB_FILES", "").split(";")
    with open(layout_path, encoding="utf-8") as f:
        layout = json.load(f)
    log("layout", True, {"racks": len(layout["racks"]), "cracs": len(layout["cracs"])})
    for (tag, asset_name), first in zip(VARIANTS, files):
        svt = import_svt(first, asset_name)
        log(f"import_{tag}", svt is not None, {"class": svt.get_class().get_name() if svt else None, "frames": svt.get_num_frames() if svt else None})
        mi = build_material(tag, svt)
        build_level(tag, mi, svt, layout)
    unreal.EditorAssetLibrary.save_directory(PKG, only_if_is_dirty=False)


def on_tick(delta):
    state["tick"] += 1
    try:
        if state["tick"] == 30:
            setup()
        if state["tick"] >= 80 and not state["done"]:
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
