"""변환 검증: numpy 원본과 OpenVDB 파일을 다시 읽은 값을 비교한다(float, half 모두). Kit 안에서 실행한다."""
from __future__ import annotations

import asyncio
import json
import os
import traceback
from pathlib import Path

import omni.kit.app

BASE = Path(os.environ.get("DCT_PROBE_OUT", "D:/Test/experiments/omniverse_probe/out"))
FRAMES = BASE / "frames"
RESULT = BASE / "kit" / "kit_vdb_roundtrip_result.json"
res: dict = {"frames": []}


async def main() -> None:
    app = omni.kit.app.get_app()
    try:
        for _ in range(30):
            await app.next_update_async()
        app.get_extension_manager().set_extension_enabled_immediate("omni.volume", True)
        for _ in range(20):
            await app.next_update_async()
        import numpy as np
        import openvdb as vdb

        meta = json.loads((FRAMES / "frames_meta.json").read_text(encoding="utf-8"))
        for fr in meta["frames"]:
            orig = np.load(FRAMES / fr["file"]).astype(np.float32)
            row = {"file": fr["file"], "t_s": fr["t_s"]}
            for suffix in ("", "_half"):
                path = FRAMES / "vdb" / (Path(fr["file"]).stem + suffix + ".vdb")
                grids = vdb.readAllGridMetadata(str(path)) if hasattr(vdb, "readAllGridMetadata") else None
                g = vdb.read(str(path), "temperature")
                back = np.full(orig.shape, float(g.background), dtype=np.float32)
                g.copyToArray(back, ijk=(0, 0, 0))
                err = np.abs(back - orig)
                row["half" if suffix else "float"] = {"max_abs_err_degC": round(float(err.max()), 4), "mean_abs_err_degC": round(float(err.mean()), 5), "orig_range": [round(float(orig.min()), 2), round(float(orig.max()), 2)], "voxel_size": float(g.transform.voxelSize()[0]), "grid_name": g.name}
            res["frames"].append(row)
        res["max_err_float"] = max(f["float"]["max_abs_err_degC"] for f in res["frames"])
        res["max_err_half"] = max(f["half"]["max_abs_err_degC"] for f in res["frames"])
    except Exception:  # noqa: BLE001
        res["fatal"] = traceback.format_exc()
        print(res["fatal"], flush=True)
    finally:
        RESULT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_vdb_roundtrip] done", {k: v for k, v in res.items() if k != "frames"}, flush=True)
        app.post_quit()


asyncio.ensure_future(main())
