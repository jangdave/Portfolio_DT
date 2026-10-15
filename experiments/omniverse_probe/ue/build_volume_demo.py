"""UE 데모 레벨 3개를 만든다: Warp 열 시뮬레이션 결과(정규화한 애니메이션 볼륨)를 UE 내장 Sparse Volume Texture Viewer로 보여 준다.

프로젝트 시작 스크립트로 실행한다. 환경 변수:
  DCT_VDB_FILES : 번호가 연속된 .vdb 중 첫 파일 경로 (TempN_000.vdb)
  DCT_UE_RESULT : 결과 JSON 경로
만들어지는 것: /Game/VolumeDemo/VolumeDemo_A, _B, _C (레벨). 에디터에서 열어 비교한다.
  A: 투명도 보통, 발광 끔 / B: 투명도 보통, 발광 켬 / C: 투명도 낮게, 발광 켬, 태양 약하게
볼륨 값은 정규화한 온도다: value = clip((T - 24) / (54 - 24), 0, 1). 주변 공기(24도 이하)는 0(빈 공간).
"""
import json
import os
import traceback

import unreal

# (이름, 투명도(extinction), 발광 광원, 태양 세기)
VARIANTS = [("A", 0.012, False, 10.0), ("B", 0.012, True, 10.0), ("C", 0.005, True, 3.0)]
result_path = os.environ.get("DCT_UE_RESULT", "D:/ue_probe/demo_result.json")
res = {"steps": {}, "variants": {}}
state = {"tick": 0, "done": False}
refs = {}


def log(name, ok, detail=None):
    res["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[ue_demo] {name}: {'OK' if ok else 'FAIL'} {detail if detail is not None else ''}", flush=True)


def save_result():
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)


def build_level(name, extinction, emissive, sun_intensity, svt):
    level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    path = f"/Game/VolumeDemo/VolumeDemo_{name}"
    ok = level_sub.new_level(path)
    info = {"new_level": bool(ok)}

    # 볼륨 뷰어: 셀 하나가 20cm라서 20배로 키워 홀 크기(8 x 6 x 3.6 m)로 맞춘다.
    # 에디터 시작 카메라가 볼륨 안에 들어가 검게 보이지 않도록 볼륨을 원점에서 떨어뜨린다.
    viewer = actor_sub.spawn_actor_from_class(unreal.SparseVolumeTextureViewer, unreal.Vector(0, 0, 0))
    viewer.set_actor_label("HallTemperature")
    comp = viewer.get_editor_property("sparse_volume_texture_viewer_component")
    comp.set_editor_property("sparse_volume_texture_preview", svt)
    comp.set_editor_property("playing", True)
    comp.set_editor_property("looping", True)
    comp.set_editor_property("frame_rate", 2.0)
    comp.set_editor_property("extinction", extinction)
    try:
        comp.set_editor_property("emissive_light_source", emissive)
    except Exception as exc:  # noqa: BLE001
        info["emissive_error"] = str(exc)
    viewer.set_actor_scale3d(unreal.Vector(20, 20, 20))
    viewer.set_actor_location(unreal.Vector(0, 0, 0), False, False)

    # 바닥
    floor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(400, 300, -2))
    floor.set_actor_label("Floor")
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(10, 8, 1))

    # 조명
    sun = actor_sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 600))
    sun.set_actor_label("Sun")
    sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-45, yaw=30), False)
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", sun_intensity)
    sky = actor_sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 700))
    sky.set_actor_label("Sky")

    # 홀을 비스듬히 보는 카메라 액터: 월드 아웃라이너에서 "Cam_Hall"을 우클릭해 Pilot Cam_Hall을 선택하면 이 시점으로 본다
    cam = actor_sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(1250, -650, 520))
    cam.set_actor_label("Cam_Hall")
    cam.set_actor_rotation(unreal.Rotator(roll=0, pitch=-19, yaw=132), False)

    info["saved"] = bool(level_sub.save_current_level())
    res["variants"][name] = {"extinction": extinction, "emissive": emissive, "sun": sun_intensity, **info}
    log(f"level_{name}", info["saved"], res["variants"][name])


def setup():
    seq_first = os.environ.get("DCT_VDB_FILES", "").split(";")[0]
    task = unreal.AssetImportTask()
    task.filename = seq_first
    task.destination_path = "/Game/VolumeDemo"
    task.destination_name = "TempN"
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objs = task.get_objects()
    svt = objs[0] if objs else None
    log("import_svt", svt is not None, {"class": svt.get_class().get_name() if svt else None, "frames": svt.get_num_frames() if svt is not None else None})
    for name, ext, emissive, sun in VARIANTS:
        build_level(name, ext, emissive, sun, svt)
    unreal.EditorAssetLibrary.save_directory("/Game/VolumeDemo", only_if_is_dirty=False)


def on_tick(delta):
    state["tick"] += 1
    try:
        if state["tick"] == 30:
            setup()
        if state["tick"] >= 60 and not state["done"]:
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
print("[ue_demo] 시작 스크립트 등록 완료", flush=True)
