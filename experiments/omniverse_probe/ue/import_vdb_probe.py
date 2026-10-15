"""R6 실증: UE 5.7에서 VDB(OpenVDB)와 NanoVDB 파일을 가져올 수 있는지 확인한다.

UnrealEditor-Cmd로 실행한다. 환경 변수:
  DCT_VDB_FILES : 가져올 파일 경로들을 ';'로 구분
  DCT_UE_RESULT : 결과 JSON 경로
각 파일을 Interchange로 가져와서 만들어진 에셋의 종류와 속성을 기록한다.
"""
from __future__ import annotations

import json
import os
import traceback

import unreal

files = [f for f in os.environ.get("DCT_VDB_FILES", "").split(";") if f]
result_path = os.environ.get("DCT_UE_RESULT", "D:/ue_probe/vdb_import_result.json")
result: dict = {"engine": unreal.SystemLibrary.get_engine_version(), "files": {}}


def describe_asset(obj) -> dict:
    d = {"class": obj.get_class().get_name(), "path": obj.get_path_name()}
    # 희소 볼륨 텍스처라면 크기와 프레임 수를 읽어 본다
    for getter in ("get_size_x", "get_size_y", "get_size_z", "get_num_frames", "get_frame_count", "get_num_mip_levels"):
        fn = getattr(obj, getter, None)
        if callable(fn):
            try:
                d[getter] = fn()
            except Exception as exc:  # noqa: BLE001
                d[getter] = f"error: {exc}"
    return d


try:
    cls = unreal.InterchangeManager
    result["interchange_manager_attrs"] = [a for a in dir(cls) if not a.startswith("_") and any(k in a for k in ("get", "import", "create", "translate", "source"))]
    mgr = None
    for name in ("get_interchange_manager_scripted", "get_interchange_manager", "get_instance"):
        fn = getattr(cls, name, None)
        if callable(fn):
            mgr = fn()
            result["manager_via"] = name
            break
    if mgr is None:
        raise RuntimeError("InterchangeManager 인스턴스를 얻지 못했다: " + str(result["interchange_manager_attrs"]))
    result["interchange_can_translate"] = {}
    for f in files:
        name = os.path.basename(f)
        entry: dict = {"exists": os.path.exists(f), "bytes": os.path.getsize(f) if os.path.exists(f) else 0}
        try:
            can = mgr.can_translate_source_data(unreal.InterchangeManager.create_source_data(f))
            entry["can_translate"] = bool(can)
        except Exception as exc:  # noqa: BLE001
            entry["can_translate_error"] = f"{type(exc).__name__}: {exc}"
        try:
            src = unreal.InterchangeManager.create_source_data(f)
            params = unreal.ImportAssetParameters()
            params.is_automated = True
            dest = "/Game/Vdb/" + os.path.splitext(name)[0].replace("-", "_")
            imported = mgr.import_asset(dest, src, params)
            entry["import_returned"] = [describe_asset(o) for o in (imported or [])]
            entry["imported_count"] = len(imported or [])
        except Exception as exc:  # noqa: BLE001
            entry["import_error"] = f"{type(exc).__name__}: {exc}"
        # 기존 방식: 콘텐츠 브라우저와 같은 가져오기(에셋 도구). Sparse Volume Texture 팩토리가 .vdb를 처리할 수 있다.
        try:
            task = unreal.AssetImportTask()
            task.filename = f
            task.destination_path = "/Game/VdbLegacy"
            task.destination_name = os.path.splitext(name)[0].replace("-", "_")
            task.automated = True
            task.save = False
            task.replace_existing = True
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            entry["legacy_imported_paths"] = [str(x) for x in task.imported_object_paths]
            entry["legacy_objects"] = [describe_asset(o) for o in task.get_objects()]
        except Exception as exc:  # noqa: BLE001
            entry["legacy_error"] = f"{type(exc).__name__}: {exc}"
        result["files"][name] = entry
        print(f"[ue_vdb] {name}: {entry}", flush=True)

    # 에셋 레지스트리에서 실제로 생긴 에셋 확인
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = list(ar.get_assets_by_path("/Game/Vdb", recursive=True)) + list(ar.get_assets_by_path("/Game/VdbLegacy", recursive=True))
    result["assets_in_game_vdb"] = [{"name": str(a.asset_name), "class": str(a.asset_class_path.asset_name)} for a in assets]
    print(f"[ue_vdb] assets: {result['assets_in_game_vdb']}", flush=True)
except Exception:  # noqa: BLE001
    result["fatal"] = traceback.format_exc()
    print(result["fatal"], flush=True)

with open(result_path, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2, ensure_ascii=False)
print("[ue_vdb] done", flush=True)
