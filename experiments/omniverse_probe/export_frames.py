"""열 시뮬레이션의 시간대별 온도장을 numpy 파일로 저장한다. (Kit 안에서 OpenVDB로 바꾸기 위한 중간 형식)

사용 (이 폴더에서): uv run --python 3.13 python export_frames.py [--dx 0.2] [--every 30]
출력: out/frames/T_<초>.npy, out/frames/frames_meta.json
- 시나리오: 240초, 60초에 CRAC_02 팬 정지. thermal_poc.py와 같은 모델이다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import warp as wp

import thermal_poc as tp

OUT = Path(__file__).resolve().parent / "out"
FRAMES = OUT / "frames"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dx", type=float, default=0.2, help="격자 간격(m)")
    ap.add_argument("--every", type=int, default=30, help="몇 초마다 저장할지")
    ap.add_argument("--duration", type=int, default=240)
    args = ap.parse_args()
    wp.config.quiet = True
    wp.init()
    tp.DX = args.dx
    tp.DT = min(0.02, 0.08 * args.dx**2 / tp.K_DIFF)  # 안정 조건 (결과 문서 참고)
    FRAMES.mkdir(parents=True, exist_ok=True)
    for old in FRAMES.glob("T_*.npy"):
        old.unlink()

    hall = tp.Hall(tp.read_scene(OUT / "poc_hall.usda"))
    steps_per_s = int(round(1.0 / tp.DT))
    hall.set_power(np.full(len(hall.scene["racks"]), 6.0, dtype=np.float32))
    saved = []
    for s in range(1, args.duration + 1):
        if s == 61:
            hall.set_fan(1, 0.0)  # 60초 지난 뒤 CRAC_02 팬 정지
        for _ in range(steps_per_s):
            hall.step()
        if s % args.every == 0:
            T = hall.T.numpy().astype(np.float32)
            np.save(FRAMES / f"T_{s:04d}.npy", T)
            saved.append({"t_s": s, "file": f"T_{s:04d}.npy", "min": round(float(T.min()), 2), "max": round(float(T.max()), 2)})
    meta = {"voxel_size_m": args.dx, "shape_xyz": [hall.nx, hall.ny, hall.nz], "background_degC": tp.T_INIT, "frames": saved}
    (FRAMES / "frames_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
