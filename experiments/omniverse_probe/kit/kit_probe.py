"""Omniverse Kit 안에서 실행되는 확인 스크립트 (R1).

Kit 앱이 시작될 때 `--exec`로 실행한다. 확인하는 것:
1. Kit 버전, 로드된 확장 중 핵심(RTX 렌더러, OmniGraph, Warp, PhysX)
2. 우리 USD 장면(poc_hall.usda) 열기와 prim 개수, 센서 앵커 수
3. Kit 안의 Warp로 GPU 커널 실행
4. 뷰포트 화면 저장
결과는 out/kit/kit_probe_result.json 과 out/kit/kit_viewport.png 에 저장하고 Kit를 종료한다.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from pathlib import Path

import carb.settings
import omni.kit.app
import omni.usd

OUT = Path(os.environ.get("DCT_KIT_OUT", "D:/Test/experiments/omniverse_probe/out/kit"))
USD_PATH = os.environ.get("DCT_KIT_USD", "D:/Test/experiments/omniverse_probe/out/poc_hall.usda")
OUT.mkdir(parents=True, exist_ok=True)

result: dict = {"steps": {}}


def step(name: str, ok: bool, detail=None):
    result["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[kit_probe] {name}: {'OK' if ok else 'FAIL'} {detail if detail is not None else ''}", flush=True)


async def main() -> None:
    app = omni.kit.app.get_app()
    try:
        result["kit_version"] = app.get_kit_version()
        result["app_name"] = carb.settings.get_settings().get("/app/name")

        # 시작이 안정되도록 몇 프레임 기다린다
        for _ in range(60):
            await app.next_update_async()

        # 1) 확장 확인
        mgr = app.get_extension_manager()
        wanted = ["omni.hydra.rtx", "omni.graph.core", "omni.warp.core", "omni.physx.stageupdate", "omni.kit.viewport.window"]
        enabled = {}
        for ext in wanted:
            enabled[ext] = bool(mgr.is_extension_enabled(ext))
        result["extensions_enabled"] = enabled
        step("extensions", all(enabled.values()), enabled)

        # 2) USD 장면 열기
        ctx = omni.usd.get_context()
        t0 = time.perf_counter()
        ok, err = await ctx.open_stage_async(USD_PATH)
        for _ in range(30):
            await app.next_update_async()
        stage = ctx.get_stage()
        n_prims = sum(1 for _ in stage.Traverse()) if stage else 0
        anchors = [p for p in stage.Traverse() if p.GetAttribute("dct:assetType") and p.GetAttribute("dct:assetType").Get() == "sensor"] if stage else []
        step("open_usd", bool(ok) and n_prims > 0, {"path": USD_PATH, "prims": n_prims, "sensor_anchors": len(anchors), "open_s": round(time.perf_counter() - t0, 2), "error": str(err) if err else None})

        # 3) Kit 안의 Warp
        try:
            import numpy as np
            import warp as wp

            wp.init()

            @wp.kernel
            def fill(a: wp.array(dtype=float), v: float):
                a[wp.tid()] = v

            dev = "cuda:0"
            arr = wp.zeros(1024, dtype=float, device=dev)
            wp.launch(fill, dim=1024, inputs=[arr, 3.5], device=dev)
            wp.synchronize_device(dev)
            ok_w = abs(float(arr.numpy().sum()) - 3.5 * 1024) < 1e-3
            devs = [{"alias": d.alias, "name": d.name, "arch": d.arch} for d in wp.get_cuda_devices()]
            step("warp_in_kit", ok_w, {"warp": wp.config.version, "devices": devs})
        except Exception as exc:  # noqa: BLE001
            step("warp_in_kit", False, f"{type(exc).__name__}: {exc}")

        # 4) 뷰포트 화면 저장
        try:
            from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

            viewport = get_active_viewport()
            for _ in range(60):  # 렌더러가 장면을 그릴 시간을 준다
                await app.next_update_async()
            png = OUT / "kit_viewport.png"
            capture = capture_viewport_to_file(viewport, str(png))
            await capture.wait_for_result(completion_frames=30)
            for _ in range(10):
                await app.next_update_async()
            step("viewport_capture", png.exists() and png.stat().st_size > 1000, {"file": png.name, "bytes": png.stat().st_size if png.exists() else 0})
        except Exception as exc:  # noqa: BLE001
            step("viewport_capture", False, f"{type(exc).__name__}: {exc}")
    except Exception:  # noqa: BLE001
        result["fatal"] = traceback.format_exc()
        print(result["fatal"], flush=True)
    finally:
        (OUT / "kit_probe_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_probe] 결과 저장, Kit 종료 요청", flush=True)
        app.post_quit()


asyncio.ensure_future(main())
