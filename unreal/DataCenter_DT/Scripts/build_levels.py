"""DataCenter_DT 프로젝트에 확인용 레벨 2개를 만든다. 에디터 시작 스크립트로 실행한다(`run_build_levels.ps1`).

  /Game/DCT/Maps/L_Hall      : 랙 60기 홀 장면(usd/scenes/hall01.usda)을 USD Stage 액터로 열고, 그 위에 열 시뮬레이션 볼륨(30프레임)을 겹친다.
  /Game/DCT/Maps/L_Exterior  : 건물 외관(usd/assets/building.usda)을 USD Stage 액터로 연다.

좌표 주의: USD(오른손 좌표계)를 Unreal(왼손 좌표계)로 가져오면 Y 부호가 뒤집힌다(ADR-010: Rack_01이 y +150 -> -150).
그래서 열 볼륨은 Y를 뒤집은 데이터(TempFY)를 쓰고 볼륨 액터를 y = -홀 길이 에 놓는다.

환경 변수: DCT_REPO(저장소 루트), DCT_VDB_FY(번호 시퀀스 첫 파일), DCT_UE_RESULT(결과 JSON)
"""
import json
import math
import os
import traceback

import unreal

REPO = os.environ.get("DCT_REPO", "D:/Test").replace("\\", "/")
HALL_USD = f"{REPO}/usd/scenes/hall01.usda"
BUILDING_USD = f"{REPO}/usd/assets/building.usda"
VDB_FY = os.environ.get("DCT_VDB_FY", f"{REPO}/experiments/omniverse_probe/out/hall60/frames/vdb_norm_flipy_seq/TempFY_000.vdb")
RESULT = os.environ.get("DCT_UE_RESULT", f"{REPO}/experiments/omniverse_probe/out/ue58_levels.json")
HALL_CM = (1100.0, 1360.0, 400.0)
PKG = "/Game/DCT"
MAPS = f"{PKG}/Maps"
VOL = f"{PKG}/Volume"
# 볼륨 저장 범위 15~45도(value = (T-15)/30). 주의 27도, 위험 32도(랙 입구 권장 상한 기준)
T_MIN, T_MAX, T_WARN, T_CRIT = 15.0, 45.0, 27.0, 32.0
WARN_N, CRIT_N = (T_WARN - T_MIN) / (T_MAX - T_MIN), (T_CRIT - T_MIN) / (T_MAX - T_MIN)
SVT_PARAM = "SparseVolumeTexture"
res = {"engine": unreal.SystemLibrary.get_engine_version(), "steps": {}}
state = {"tick": 0, "done": False, "stage": None}
refs = {}
mel = unreal.MaterialEditingLibrary
level_sub = None
actor_sub = None


def log(name, ok, detail=None):
    res["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[dct_levels] {name}: {'OK' if ok else 'FAIL'} {str(detail)[:400] if detail is not None else ''}", flush=True)


def save_result():
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False, default=str)


# ---- 볼륨 머티리얼 (실험 `build_heat_demo.py`와 같은 구조: 값 -> 색 램프, 불투명도, 발광) ----
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


def build_material(svt):
    atools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = atools.create_asset("M_TempVolume", VOL, unreal.Material, unreal.MaterialFactoryNew())
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
    res["sample_connected"] = bool(mel.connect_material_expressions(smp, "Attributes A", mask, ""))
    v = mask
    c_cool, c_warn = color(mat, (0.03, 0.2, 1.0), -700, -700), color(mat, (1.0, 0.85, 0.05), -700, -600)
    c_crit, c_hot = color(mat, (1.0, 0.12, 0.02), -700, -500), color(mat, (1.0, 0.92, 0.8), -700, -400)
    a1 = remap01(mat, v, 0.0, WARN_N, -700, -100)
    a2 = remap01(mat, v, WARN_N, CRIT_N, -700, 100)
    a3 = remap01(mat, v, CRIT_N, 1.0, -700, 300)
    ramp = lerp(mat, lerp(mat, lerp(mat, c_cool, c_warn, a1, -200, -600), c_crit, a2, 0, -500), c_hot, a3, 200, -400)
    contrast = param(mat, "Contrast", 1.2, 0, 700)
    density = param(mat, "DensityScale", 0.01, 0, 800)
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
    mi = atools.create_asset("MI_TempVolume", VOL, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", mat)
    mel.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


def import_svt(first_file, name):
    task = unreal.AssetImportTask()
    task.filename = first_file
    task.destination_path = VOL
    task.destination_name = name
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objs = task.get_objects()
    return objs[0] if objs else None


# ---- 장면 구성 ----
def open_stage(usd_path, label):
    actor = actor_sub.spawn_actor_from_class(unreal.UsdStageActor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(label)
    actor.set_editor_property("use_prim_kinds_for_collapsing", False)  # prim마다 컴포넌트를 만든다(앵커와 장비를 구분하려면 필요)
    actor.set_editor_property("root_layer", unreal.FilePath(usd_path))
    return actor


def world_bounds(actor, keys):
    """이름에 keys 중 하나가 들어간 컴포넌트의 월드 위치 범위(cm)."""
    pts = []
    for c in actor.root_component.get_children_components(True):
        if any(k in c.get_name() for k in keys):
            loc = c.get_world_location()
            pts.append((loc.x, loc.y, loc.z))
    if not pts:
        return None
    lo = [round(min(p[i] for p in pts), 1) for i in range(3)]
    hi = [round(max(p[i] for p in pts), 1) for i in range(3)]
    return {"count": len(pts), "min": lo, "max": hi}


def look_at(cam, eye, target):
    yaw = math.degrees(math.atan2(target[1] - eye[1], target[0] - eye[0]))
    pitch = math.degrees(math.atan2(target[2] - eye[2], math.hypot(target[0] - eye[0], target[1] - eye[1])))
    cam.set_actor_rotation(unreal.Rotator(roll=0, pitch=pitch, yaw=yaw), False)


def add_camera(label, eye, target):
    cam = actor_sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*eye))
    cam.set_actor_label(label)
    look_at(cam, eye, target)
    return cam


def start_hall():
    W, L, H = HALL_CM
    level_sub.new_level(f"{MAPS}/L_Hall")
    stage = open_stage(HALL_USD, "HallStage")
    state["stage"] = stage
    # 열 볼륨: Y를 뒤집은 데이터, 최소 모서리를 (0, -홀 길이, 0)에 둔다
    svt = import_svt(VDB_FY, "TempFY")
    log("import_volume", svt is not None, {"class": svt.get_class().get_name() if svt else None, "frames": svt.get_num_frames() if svt else None, "size": (svt.get_size_x(), svt.get_size_y(), svt.get_size_z()) if svt else None})
    mi = build_material(svt)
    hv = actor_sub.spawn_actor_from_class(unreal.HeterogeneousVolume, unreal.Vector(0, -L, 0))
    hv.set_actor_label("HallTemperature")
    comp = hv.get_editor_property("heterogeneous_volume_component")
    comp.set_material(0, mi)
    for name, value in (("volume_resolution", unreal.IntVector(svt.get_size_x(), svt.get_size_y(), svt.get_size_z())), ("playing", True), ("looping", True), ("frame_rate", 2.0), ("start_frame", 0.0), ("end_frame", float(svt.get_num_frames() - 1))):
        try:
            comp.set_editor_property(name, value)
        except Exception as exc:  # noqa: BLE001
            res.setdefault("volume_prop_failures", {})[name] = str(exc)[:80]
    hv.set_actor_scale3d(unreal.Vector(1, 1, 1))
    # 조명: 홀 안쪽은 천장으로 막혀 있어서 점 조명을 천장 아래에 격자로 놓는다
    n = 0
    for ix in range(3):
        for iy in range(4):
            x = W * (ix + 0.5) / 3
            y = -L * (iy + 0.5) / 4
            lt = actor_sub.spawn_actor_from_class(unreal.PointLight, unreal.Vector(x, y, H - 30))
            lt.set_actor_label(f"HallLight_{n:02d}")
            comp_l = lt.get_component_by_class(unreal.PointLightComponent)
            comp_l.set_editor_property("intensity", 6000.0)
            comp_l.set_editor_property("attenuation_radius", 1400.0)
            n += 1
    actor_sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(W / 2, -L / 2, H + 200))
    add_camera("Cam_HallOverview", (W - 80, -120, 300), (W * 0.4, -L * 0.55, 90))
    ps = actor_sub.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(W / 2, -L / 2, 100))
    ps.set_actor_label("PlayerStart_Hall")
    log("hall_stage_opened", True, {"usd": HALL_USD, "volume_location_cm": [0, -L, 0]})


def report_hall():
    stage = state["stage"]
    comps = stage.root_component.get_children_components(True)
    info = {
        "stage_state": str(stage.get_editor_property("stage_state")),
        "components": len(comps),
        "racks": world_bounds(stage, ["Rack_"]) if False else None,
    }
    rack_names = [c for c in comps if c.get_name().startswith("Rack_") and "Anchors" not in c.get_name() and "_U" not in c.get_name() and c.get_name().rsplit("_", 1)[0] == "Rack_" + c.get_name().split("_")[1]]
    info["Rack_"] = sum(1 for c in comps if c.get_name().startswith("Rack_"))
    info["CRAC_"] = sum(1 for c in comps if c.get_name().startswith("CRAC_"))
    info["Sensor_"] = sum(1 for c in comps if c.get_name().startswith("Sensor_"))
    info["Vent_"] = sum(1 for c in comps if c.get_name().startswith("Vent_"))
    info["rack_bounds_cm"] = world_bounds(stage, ["Rack_01_0", "Rack_60_0", "Rack_10_0", "Rack_51_0"])
    info["expected_y_range_cm"] = [-HALL_CM[1], 0]
    log("hall_stage_report", info["Rack_"] == 60 and info["CRAC_"] == 8, info)


def start_exterior():
    level_sub.save_current_level()
    level_sub.new_level(f"{MAPS}/L_Exterior")
    stage = open_stage(BUILDING_USD, "BuildingStage")
    state["stage"] = stage
    sun = actor_sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 3000))
    sun.set_actor_label("Sun")
    sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-38, yaw=35), False)
    sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_comp.set_editor_property("intensity", 8.0)
    try:
        sun_comp.set_editor_property("atmosphere_sun_light", True)
    except Exception as exc:  # noqa: BLE001
        res["sun_flag_error"] = str(exc)[:80]
    actor_sub.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
    actor_sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 2000))
    actor_sub.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
    # 건물 앞(USD -Y)은 Unreal에서 +Y다. 정문 쪽 비스듬한 위에서 본다.
    add_camera("Cam_Exterior", (-6500, 9500, 2800), (0, 0, 600))
    ps = actor_sub.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, 6500, 100))
    ps.set_actor_label("PlayerStart_Exterior")
    log("exterior_stage_opened", True, {"usd": BUILDING_USD})


def report_exterior():
    stage = state["stage"]
    comps = stage.root_component.get_children_components(True)
    names = [c.get_name() for c in comps]
    locs = [c.get_world_location() for c in comps]
    info = {
        "stage_state": str(stage.get_editor_property("stage_state")),
        "components": len(comps),
        "first": names[:6],
        "x_range_cm": [round(min(l.x for l in locs), 1), round(max(l.x for l in locs), 1)] if locs else None,
        "y_range_cm": [round(min(l.y for l in locs), 1), round(max(l.y for l in locs), 1)] if locs else None,
        "z_range_cm": [round(min(l.z for l in locs), 1), round(max(l.z for l in locs), 1)] if locs else None,
        "has_exterior": any(n.startswith("Exterior") for n in names),
        "has_outdoor": any(n.startswith("Outdoor") for n in names),
        "has_floors": any(n.startswith("Floors") for n in names),
    }
    log("exterior_stage_report", len(comps) > 10, info)


def on_tick(delta):
    global level_sub, actor_sub
    state["tick"] += 1
    t = state["tick"]
    try:
        if t == 30:
            level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            start_hall()
        if t == 330:
            report_hall()
            level_sub.save_current_level()
            log("save_hall", True, f"{MAPS}/L_Hall")
        if t == 340:
            start_exterior()
        if t == 700:
            report_exterior()
            level_sub.save_current_level()
            log("save_exterior", True, f"{MAPS}/L_Exterior")
        if t >= 720 and not state["done"]:
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
print("[dct_levels] 등록 완료", flush=True)
