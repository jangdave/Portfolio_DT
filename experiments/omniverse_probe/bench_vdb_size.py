"""부피 데이터(NanoVDB) 용량을 해상도와 압축 방식별로 측정한다.

사용 (이 폴더에서): uv run --python 3.13 python bench_vdb_size.py
- 같은 열 시뮬레이션(240초, CRAC 고장)을 격자 간격 20cm, 10cm로 돌려 마지막 프레임을 저장한다.
- 압축: none, zip, blosc. 다시 읽어 복셀 수가 같은지 확인한다.
- 240프레임(시나리오 1초당 1프레임) 저장 시 예상 용량을 계산한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import warp as wp

import thermal_poc as tp

OUT = Path(__file__).resolve().parent / "out"
TMP = OUT / "_vdb_size_tmp"


def run_field(dx: float) -> np.ndarray:
    tp.DX = dx
    tp.DT = min(0.02, 0.08 * dx * dx / tp.K_DIFF)  # 안정 조건 (결과 문서 참고)
    hall = tp.Hall(tp.read_scene(OUT / "poc_hall.usda"))
    steps_per_s = int(round(1.0 / tp.DT))
    powers = np.full(len(hall.scene["racks"]), 6.0, dtype=np.float32)
    hall.set_power(powers)
    for s in range(240):
        if s == 60:
            hall.set_fan(1, 0.0)
        for _ in range(steps_per_s):
            hall.step()
    wp.synchronize_device(hall.device)
    return hall.T.numpy().astype(np.float32)


def main() -> None:
    wp.config.quiet = True
    wp.init()
    TMP.mkdir(exist_ok=True)
    rows = []
    for dx in (0.20, 0.10):
        T = run_field(dx)
        vol = wp.Volume.load_from_numpy(T, min_world=(0.0, 0.0, 0.0), voxel_size=dx, bg_value=22.0, device="cuda:0")
        for codec in ("none", "zip", "blosc"):
            path = TMP / f"T_dx{int(dx*100)}_{codec}.nvdb"
            try:
                vol.save_to_nvdb(str(path), codec=codec)
                with open(path, "rb") as f:
                    back = wp.Volume.load_from_nvdb(f, device="cuda:0")
                rows.append(
                    {
                        "dx_cm": int(dx * 100),
                        "cells": int(T.size),
                        "codec": codec,
                        "file_kib": round(path.stat().st_size / 1024, 1),
                        "reload_voxels": int(back.get_voxel_count()),
                        "est_240_frames_mb": round(path.stat().st_size * 240 / 1e6, 1),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                rows.append({"dx_cm": int(dx * 100), "codec": codec, "error": f"{type(exc).__name__}: {exc}"})
    (OUT / "bench_vdb_size.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(r)
    for p in TMP.glob("*"):
        p.unlink()
    TMP.rmdir()


if __name__ == "__main__":
    main()
