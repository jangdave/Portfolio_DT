"""Kit 안에서 numpy 온도 프레임을 OpenVDB(.vdb) 파일로 바꾼다. (Kit의 omni.volume 확장이 openvdb Python 모듈을 포함한다)

입력: out/frames/T_*.npy + frames_meta.json    출력: out/frames/vdb/T_*.vdb, out/kit/kit_npy_to_vdb_result.json
Kit의 Python은 3.12이고 numpy가 함께 들어 있다.
"""
from __future__ import annotations

import asyncio
import json
import os
import traceback
from pathlib import Path

import omni.kit.app

BASE = Path(os.environ.get("DCT_PROBE_OUT", "D:/Test/experiments/omniverse_probe/out"))
FRAMES = BASE / "frames"
VDB_OUT = FRAMES / "vdb"
RESULT = BASE / "kit" / "kit_npy_to_vdb_result.json"
res: dict = {"frames": []}


async def main() -> None:
    app = omni.kit.app.get_app()
    try:
        for _ in range(30):
            await app.next_update_async()
        mgr = app.get_extension_manager()
        mgr.set_extension_enabled_immediate("omni.volume", True)
        for _ in range(20):
            await app.next_update_async()

        import numpy as np
        import openvdb as vdb

        res["openvdb_module"] = getattr(vdb, "__file__", "?")
        res["openvdb_version"] = str(getattr(vdb, "__version__", getattr(vdb, "LIBRARY_VERSION_STRING", "?")))
        meta = json.loads((FRAMES / "frames_meta.json").read_text(encoding="utf-8"))
        voxel = float(meta["voxel_size_m"])
        bg = float(meta["background_degC"])
        VDB_OUT.mkdir(parents=True, exist_ok=True)

        for fr in meta["frames"]:
            arr = np.load(FRAMES / fr["file"]).astype(np.float32)
            grid = vdb.FloatGrid(bg)  # 배경값 = 주변 공기 온도
            grid.name = "temperature"
            grid.transform = vdb.createLinearTransform(voxelSize=voxel)
            grid.copyFromArray(arr, ijk=(0, 0, 0), tolerance=0.01)  # 배경과 거의 같은 칸은 저장하지 않는다(희소)
            for half in (False, True):
                grid.saveFloatAsHalf = half
                out = VDB_OUT / (Path(fr["file"]).stem + ("_half" if half else "") + ".vdb")
                vdb.write(str(out), grids=[grid])
                res["frames"].append({"file": out.name, "bytes": out.stat().st_size, "half": half, "active_voxels": int(grid.activeVoxelCount()), "dense_cells": int(arr.size)})
        res["ok"] = all(f["bytes"] > 0 for f in res["frames"]) and len(res["frames"]) > 0
    except Exception:  # noqa: BLE001
        res["fatal"] = traceback.format_exc()
        print(res["fatal"], flush=True)
    finally:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_npy_to_vdb] done", json.dumps({k: v for k, v in res.items() if k != "frames"}, ensure_ascii=False), flush=True)
        app.post_quit()


asyncio.ensure_future(main())
