"""열 시뮬레이션의 계산 속도와 해상도별 확장성을 독립적으로 측정한다.

사용 (이 폴더에서): uv run --python 3.13 python bench_thermal.py
- 격자 간격을 10cm, 5cm, 2.5cm로 바꿔 가며 같은 장면을 돌리고, GPU 동기화 후 시간을 잰다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import warp as wp

import thermal_poc as tp

OUT = Path(__file__).resolve().parent / "out"


def run(dx: float, steps: int = 4000) -> dict:
    tp.DX = dx
    # 안정 조건: 확산 계수 K*dt/dx^2 가 0.1 이하가 되게 dt를 정한다.
    # (이론상 한계는 1/6이지만 0.16에서 실제로 발산했다. 여유를 둔다.)
    tp.DT = min(0.02, 0.08 * dx * dx / tp.K_DIFF)
    scene_path = OUT / "poc_hall.usda"
    scene = tp.read_scene(scene_path)
    t0 = time.perf_counter()
    hall = tp.Hall(scene)
    setup_s = time.perf_counter() - t0
    for _ in range(50):  # 예열(컴파일 포함)
        hall.step()
    wp.synchronize_device(hall.device)
    t0 = time.perf_counter()
    for _ in range(steps):
        hall.step()
    wp.synchronize_device(hall.device)
    wall = time.perf_counter() - t0
    sim_s = steps * tp.DT
    T = hall.T.numpy()
    return {
        "dx_cm": dx * 100,
        "dt_s": tp.DT,
        "k_dt_over_dx2": round(tp.K_DIFF * tp.DT / dx**2, 3),
        "cells": hall.n_cells,
        "steps": steps,
        "wall_s": round(wall, 3),
        "steps_per_s": round(steps / wall),
        "gcell_updates_per_s": round(hall.n_cells * steps / wall / 1e9, 2),
        "sim_seconds_per_wall_second": round(sim_s / wall, 1),
        "grid_setup_s_python": round(setup_s, 2),
        "T_finite": bool(np.isfinite(T).all()),
        "bytes_per_cell_estimate": 32,
        "effective_GB_per_s_estimate": round(hall.n_cells * steps * 32 / wall / 1e9),
        "T_range": [round(float(T.min()), 1), round(float(T.max()), 1)],
    }


def main() -> None:
    wp.config.quiet = True
    wp.init()
    results = [run(0.10, 4000), run(0.05, 2000), run(0.025, 1000)]
    (OUT / "bench_thermal.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
