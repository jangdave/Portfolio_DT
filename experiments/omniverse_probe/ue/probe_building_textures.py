"""UE 5.8에서 건물 USD를 Stage 액터로 연 뒤, 재질에 연결된 텍스처의 가져오기 설정(sRGB, 압축, 크기)을 읽는다.

보려는 것: 거칠기와 노멀 텍스처가 색상(sRGB)으로 읽히지 않았는지. 거칠기가 sRGB로 읽히면 값이 어두워져 표면이 훨씬 매끈하게(번쩍이게) 보인다.
실행기: run_usd_probe.ps1 -Script probe_building_textures.py -Usd <건물.usda>
"""
import json
import os
import traceback

import unreal

USD = os.environ.get("DCT_USD", "D:/Test/usd/assets/building.usda")
RESULT = os.environ.get("DCT_UE_RESULT", "D:/Test/experiments/omniverse_probe/out/ue58_building_textures.json")
res = {"usd": USD, "engine": unreal.SystemLibrary.get_engine_version(), "materials": {}}
state = {"tick": 0, "done": False}
refs = {}


def save():
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False, default=str)


def open_stage():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = sub.spawn_actor_from_class(unreal.UsdStageActor, unreal.Vector(0, 0, 0))
    actor.set_editor_property("use_prim_kinds_for_collapsing", False)
    actor.set_editor_property("root_layer", unreal.FilePath(USD))
    refs["actor"] = actor


def describe(tex):
    d = {"class": tex.get_class().get_name()}
    for p in ("srgb", "compression_settings", "mip_gen_settings", "lod_group", "max_texture_size", "never_stream", "flip_green_channel", "address_x"):
        try:
            d[p] = str(tex.get_editor_property(p))
        except Exception as exc:  # noqa: BLE001
            d[p] = "읽기 실패: " + str(exc)[:40]
    try:
        d["size"] = [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
    except Exception:  # noqa: BLE001
        pass
    return d


def report():
    actor = refs["actor"]
    comps = actor.root_component.get_children_components(True)
    seen = {}
    for c in comps:
        try:
            mats = c.get_materials()
        except Exception:  # noqa: BLE001
            continue
        for m in mats:
            if m is None or m.get_name() in seen:
                continue
            seen[m.get_name()] = m
    res["component_count"] = len(comps)
    for name, m in seen.items():
        item = {"class": m.get_class().get_name()}
        texs = {}
        try:
            item["parent"] = m.get_editor_property("parent").get_name()
            for tv in m.get_editor_property("texture_parameter_values"):
                tex = tv.get_editor_property("parameter_value")
                if tex is not None:
                    texs[f"{tv.get_editor_property('parameter_info').get_editor_property('name')} = {tex.get_name()}"] = tex
        except Exception as exc:  # noqa: BLE001
            item["error"] = str(exc)[:80]
        item["textures"] = {k: describe(t) for k, t in texs.items()}
        res["materials"][name] = item
    print("[tex_probe] 재질", len(seen), "개", flush=True)


def on_tick(delta):
    state["tick"] += 1
    try:
        if state["tick"] == 20:
            open_stage()
        if state["tick"] == 260:
            report()
        if state["tick"] >= 280 and not state["done"]:
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
