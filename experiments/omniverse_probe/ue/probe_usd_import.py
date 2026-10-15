"""UE 5.8에서 홀 장면(USD)을 가져오는 두 가지 방법을 시험한다.

1) Interchange 가져오기(AssetImportTask): 파일을 에셋과 레벨 액터로 바꾼다.
2) USD Stage 액터(UsdStageActor): 파일을 열어 두고 prim을 액터로 보여 준다. 실행 중에도 prim 속성을 읽을 수 있는지 확인한다.

보려는 것: 랙, CRAC, 센서 앵커가 몇 개 생기는지, `dct:` 사용자 속성(assetType, sensorId, metric)을 읽을 수 있는지, 위치가 맞는지.
실행: UnrealEditor.exe <프로젝트> -ExecutePythonScript=<이 파일> -nosplash -RenderOffScreen
환경 변수: DCT_USD(장면 파일), DCT_UE_RESULT(결과 JSON)
"""
import json
import os
import traceback

import unreal

USD = os.environ.get("DCT_USD", "D:/Test/usd/scenes/hall01.usda")
RESULT = os.environ.get("DCT_UE_RESULT", "D:/Test/experiments/omniverse_probe/out/ue58_usd_probe.json")
res = {"usd": USD, "engine": unreal.SystemLibrary.get_engine_version(), "steps": {}}
state = {"tick": 0, "done": False}
refs = {}


def log(name, ok, detail=None):
    res["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[usd_probe] {name}: {'OK' if ok else 'FAIL'} {str(detail)[:300] if detail is not None else ''}", flush=True)


def save():
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False, default=str)


def probe_interchange():
    task = unreal.AssetImportTask()
    task.filename = USD
    task.destination_path = "/Game/UsdProbe"
    task.automated = True
    task.save = False
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objs = list(task.get_objects())
    classes = {}
    for o in objs:
        classes[o.get_class().get_name()] = classes.get(o.get_class().get_name(), 0) + 1
    assets = unreal.EditorAssetLibrary.list_assets("/Game/UsdProbe", recursive=True, include_folder=False)
    log("interchange_import", len(objs) > 0, {"objects": len(objs), "classes": classes, "assets_under_path": len(assets), "sample": [a for a in assets[:6]]})


def probe_stage_actor():
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actor_sub.spawn_actor_from_class(unreal.UsdStageActor, unreal.Vector(0, 0, 0))
    res["stage_actor_methods"] = [m for m in dir(actor) if not m.startswith("_") and any(k in m.lower() for k in ("prim", "stage", "layer", "attr", "metadata", "root"))][:60]
    try:
        # prim 종류(kind)로 하나의 컴포넌트에 합치지 않고 prim마다 컴포넌트를 만든다. 사용자 속성(dct:*)을 컴포넌트에 수집한다.
        actor.set_editor_property("use_prim_kinds_for_collapsing", False)
        opts = actor.get_editor_property("metadata_options")
        opts.set_editor_property("collect_metadata", True)
        opts.set_editor_property("collect_on_components", True)
        opts.set_editor_property("collect_from_entire_subtrees", True)
        actor.set_editor_property("metadata_options", opts)
        actor.set_editor_property("root_layer", unreal.FilePath(USD))
        log("stage_actor_open", True, {"root_layer": str(actor.get_editor_property("root_layer"))})
    except Exception as exc:  # noqa: BLE001
        log("stage_actor_open", False, str(exc))
    refs["actor"] = actor


def report_stage():
    """Stage 액터가 만든 컴포넌트와 prim 속성(metadata) 접근을 확인한다."""
    actor = refs.get("actor")
    if actor is None:
        return
    root = actor.root_component
    comps = root.get_children_components(True)
    names = [c.get_name() for c in comps]
    cnt = lambda key: sum(1 for n in names if key in n)
    info = {"components": len(comps), "Rack_": cnt("Rack_"), "CRAC_": cnt("CRAC_"), "Sensor_": cnt("Sensor_"), "first": names[:8]}
    res["stage_state"] = str(actor.get_editor_property("stage_state")) if "stage_state" in dir(actor) else None
    try:
        res["metadata_options"] = str(actor.get_editor_property("metadata_options"))
    except Exception as exc:  # noqa: BLE001
        res["metadata_options"] = "읽기 실패: " + str(exc)[:80]
    # Rack_01 컴포넌트에서 사용자 속성 찾기
    target = next((c for c in comps if c.get_name() == "Rack_01"), None) or next((c for c in comps if "Rack_01" in c.get_name()), None)
    if target is not None:
        info["rack_01_class"] = target.get_class().get_name()
        try:
            info["rack_01_world_loc_cm"] = [round(v, 1) for v in (target.get_world_location().x, target.get_world_location().y, target.get_world_location().z)]
        except Exception as exc:  # noqa: BLE001
            info["rack_01_world_loc_cm"] = "실패: " + str(exc)[:80]
        def read_meta(comp):
            try:
                aud = comp.get_editor_property("asset_user_data")
                out = []
                for x in aud:
                    item = {"class": x.get_class().get_name(), "methods": [m for m in dir(x) if not m.startswith("_") and ("meta" in m.lower() or "prim" in m.lower() or "stage" in m.lower())][:20]}
                    for prop in ("prim_paths", "stage_identifier_to_metadata"):
                        try:
                            item[prop] = str(x.get_editor_property(prop))[:600]
                        except Exception as exc:  # noqa: BLE001
                            item[prop] = "읽기 실패: " + str(exc)[:80]
                    out.append(item)
                return out
            except Exception as exc:  # noqa: BLE001
                return "읽기 실패: " + str(exc)[:80]

        info["rack_01_metadata"] = read_meta(target)
        sensor = next((c for c in comps if c.get_name().startswith("Sensor_TEMP_IN") ), None)
        if sensor is not None:
            info["sensor_name"] = sensor.get_name()
            info["sensor_metadata"] = read_meta(sensor)
    log("stage_components", len(comps) > 0, info)


def report_level():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    names = [a.get_actor_label() for a in actors]
    rack_like = [n for n in names if n.startswith("Rack_") or "Rack" in n]
    crac_like = [n for n in names if "CRAC" in n]
    sensor_like = [n for n in names if "Sensor" in n]
    tags = {}
    for a in actors:
        t = [str(x) for x in a.tags]
        if t:
            tags[a.get_actor_label()] = t[:5]
    log("level_actors", len(actors) > 0, {"actors": len(actors), "rack_like": len(rack_like), "crac_like": len(crac_like), "sensor_like": len(sensor_like), "first_names": names[:12], "actors_with_tags": dict(list(tags.items())[:5])})
    # 위치 확인: Rack_01의 월드 위치(cm). 장면 기준 (280+30? 아래 build_scene 규칙) x=310, y=150
    for a in actors:
        if a.get_actor_label() == "Rack_01":
            loc = a.get_actor_location()
            res["rack_01_location_cm"] = [round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)]
            res["rack_01_class"] = a.get_class().get_name()
            break
    # 사용자 속성 접근: 액터 / 컴포넌트에서 metadata 또는 asset user data를 찾는다
    for a in actors:
        if a.get_actor_label() == "Rack_01":
            comps = a.get_components_by_class(unreal.SceneComponent)
            res["rack_01_components"] = [c.get_name() + ":" + c.get_class().get_name() for c in comps][:10]
            break


def on_tick(delta):
    state["tick"] += 1
    try:
        if state["tick"] == 20:
            probe_interchange()
        if state["tick"] == 40:
            probe_stage_actor()
        if state["tick"] == 120:
            report_stage()
            report_level()
        if state["tick"] >= 140 and not state["done"]:
            state["done"] = True
            save()
            unreal.unregister_slate_post_tick_callback(refs["h"])
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
    except Exception:  # noqa: BLE001
        res["tick_error"] = traceback.format_exc()
        print(res["tick_error"], flush=True)
        state["done"] = True
        save()
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


refs["h"] = unreal.register_slate_post_tick_callback(on_tick)
print("[usd_probe] 등록 완료", flush=True)
