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
        # 정규화 버전: 온도를 0~1로 바꾸고 주변 공기(TMIN 이하)를 0(빈 공간)으로 둔다. UE에서 열이 뭉친 곳만 보이게 한다.
        tmin = float(os.environ.get("DCT_TMIN", "20"))
        tmax = float(os.environ.get("DCT_TMAX", "55"))
        sub = os.environ.get("DCT_OUTSUB", "vdb_norm")  # 출력 폴더 이름 앞부분 (변환 규약별로 구분)
        norm_dir = FRAMES / sub
        norm_dir.mkdir(parents=True, exist_ok=True)
        res["normalize"] = {"tmin_degC": tmin, "tmax_degC": tmax, "formula": "value = clip((T - tmin) / (tmax - tmin), 0, 1)"}
        res["normalized_frames"] = []
        for fr in meta["frames"]:
            arr = np.load(FRAMES / fr["file"]).astype(np.float32)
            nrm = np.clip((arr - tmin) / (tmax - tmin), 0.0, 1.0).astype(np.float32)
            grid = vdb.FloatGrid(0.0)
            grid.name = "temperature"
            grid.transform = vdb.createLinearTransform(voxelSize=voxel)
            grid.copyFromArray(nrm, ijk=(0, 0, 0), tolerance=0.002)  # 거의 0인 칸은 저장하지 않는다(희소)
            out = norm_dir / (Path(fr["file"]).stem + ".vdb")
            vdb.write(str(out), grids=[grid])
            res["normalized_frames"].append({"file": out.name, "bytes": out.stat().st_size, "active_voxels": int(grid.activeVoxelCount()), "dense_cells": int(nrm.size), "max_value": round(float(nrm.max()), 3)})
        # 축 뒤집은 변형: UE의 SVT 임포터는 VDB 변환의 부호를 무시하고 격자 인덱스를 그대로 쓴다는 실무 기록이 있어,
        # 모델과 맞는 방향을 눈으로 확인하려고 X, Y 축을 뒤집은 버전도 만든다. (Z는 높이라 뒤집지 않는다)
        res["flips"] = {}
        for flip_name, axis in (("flipx", 0), ("flipy", 1)):
            fdir = FRAMES / f"{sub}_{flip_name}"
            fdir.mkdir(parents=True, exist_ok=True)
            res["flips"][flip_name] = []
            for fr in meta["frames"]:
                arr = np.load(FRAMES / fr["file"]).astype(np.float32)
                nrm = np.flip(np.clip((arr - tmin) / (tmax - tmin), 0.0, 1.0), axis=axis).astype(np.float32).copy()
                grid = vdb.FloatGrid(0.0)
                grid.name = "temperature"
                grid.transform = vdb.createLinearTransform(voxelSize=voxel)
                grid.copyFromArray(nrm, ijk=(0, 0, 0), tolerance=0.002)
                out = fdir / (Path(fr["file"]).stem + ".vdb")
                vdb.write(str(out), grids=[grid])
                res["flips"][flip_name].append(out.name)
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
