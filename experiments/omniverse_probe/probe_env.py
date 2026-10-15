"""환경 확인: Warp가 RTX 5090에서 실제로 커널을 실행하는지, 라이브러리 버전을 기록한다.

사용 (이 폴더에서): uv run --python 3.13 python probe_env.py
"""
from __future__ import annotations

import importlib.metadata as md
import json
import sys
import time
from pathlib import Path

import numpy as np
import warp as wp

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


@wp.kernel
def saxpy(a: float, x: wp.array(dtype=float), y: wp.array(dtype=float)):
    i = wp.tid()
    y[i] = a * x[i] + y[i]


def main() -> None:
    wp.config.quiet = True
    wp.init()
    result: dict = {
        "python": sys.version.split()[0],
        "versions": {n: md.version(n) for n in ("warp-lang", "usd-core", "ovrtx", "ovphysx", "numpy")},
        "warp_cuda_devices": [],
    }
    for d in wp.get_cuda_devices():
        result["warp_cuda_devices"].append(
            {"alias": d.alias, "name": d.name, "arch": d.arch, "total_memory_mib": d.total_memory // (1024 * 1024)}
        )
    result["warp_cuda_driver_version"] = wp.get_cuda_driver_version() if hasattr(wp, "get_cuda_driver_version") else None

    # 실제 커널 실행: 컴파일 시간과 실행 결과 확인
    dev = "cuda:0"
    n = 1 << 22
    x = wp.array(np.ones(n, dtype=np.float32), device=dev)
    y = wp.array(np.full(n, 2.0, dtype=np.float32), device=dev)
    t0 = time.perf_counter()
    wp.launch(saxpy, dim=n, inputs=[3.0, x, y], device=dev)
    wp.synchronize_device(dev)
    result["first_launch_s_including_compile"] = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    for _ in range(100):
        wp.launch(saxpy, dim=n, inputs=[3.0, x, y], device=dev)
    wp.synchronize_device(dev)
    result["launch_100x_4M_elems_s"] = round(time.perf_counter() - t0, 4)
    got = float(y.numpy()[0])
    result["kernel_result_ok"] = abs(got - (2.0 + 3.0 * 101)) < 1e-3  # 처음 1회 + 100회 반복

    (OUT / "env_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
