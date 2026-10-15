"""Kit 안에서 Flow(연기·유체) 확장을 켤 수 있는지와 관련 기능을 확인한다 (R2의 첫 단계).

실행은 kit_probe.py와 같은 방식(--exec). 결과: out/kit/kit_flow_result.json
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from pathlib import Path

import omni.kit.app
import omni.usd

OUT = Path(os.environ.get("DCT_KIT_OUT", "D:/Test/experiments/omniverse_probe/out/kit"))
OUT.mkdir(parents=True, exist_ok=True)
result: dict = {"extensions": {}}


async def try_enable(app, mgr, ext_id: str) -> dict:
    info: dict = {}
    t0 = time.perf_counter()
    try:
        mgr.set_extension_enabled_immediate(ext_id, True)
        for _ in range(30):
            await app.next_update_async()
        info["enabled"] = bool(mgr.is_extension_enabled(ext_id))
    except Exception as exc:  # noqa: BLE001
        info["enabled"] = False
        info["error"] = f"{type(exc).__name__}: {exc}"
    info["seconds"] = round(time.perf_counter() - t0, 1)
    # 설치된 확장 목록에서 버전 찾기
    try:
        for e in mgr.get_extensions():
            if e.get("name") == ext_id or str(e.get("id", "")).startswith(ext_id + "-"):
                info["id"] = e.get("id")
                info["enabled_state"] = e.get("enabled")
                break
    except Exception:  # noqa: BLE001
        pass
    return info


async def main() -> None:
    app = omni.kit.app.get_app()
    try:
        t_start = time.perf_counter()
        for _ in range(30):
            await app.next_update_async()
        mgr = app.get_extension_manager()
        for ext in ("omni.flowusd", "omni.usd.schema.flow", "omni.kit.window.script_editor", "omni.graph.window.core"):
            result["extensions"][ext] = await try_enable(app, mgr, ext)
            print(f"[kit_flow] {ext}: {result['extensions'][ext]}", flush=True)

        # Flow 스키마가 USD에 등록되었는지 (Flow prim 종류가 있는지) 확인
        try:
            from pxr import Plug, Tf

            types = [t.typeName for t in Tf.Type.FindByName("UsdSchemaBase").GetAllDerivedTypes()]
            flow_types = sorted(t for t in types if "Flow" in t)
            result["usd_flow_schema_types"] = flow_types[:40]
            print(f"[kit_flow] Flow 스키마 타입 {len(flow_types)}개: {flow_types[:10]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            result["usd_flow_schema_types_error"] = f"{type(exc).__name__}: {exc}"

        result["startup_to_probe_s"] = round(time.perf_counter() - t_start, 1)
        result["app_uptime_s_at_probe"] = round(app.get_time_since_start_s(), 1) if hasattr(app, "get_time_since_start_s") else None
    except Exception:  # noqa: BLE001
        result["fatal"] = traceback.format_exc()
        print(result["fatal"], flush=True)
    finally:
        (OUT / "kit_flow_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_flow] 완료, 종료 요청", flush=True)
        app.post_quit()


asyncio.ensure_future(main())
