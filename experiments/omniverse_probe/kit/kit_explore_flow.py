"""Kit 안의 Flow 관련 명령과 Python API 이름을 조사한다 (Flow 시뮬레이션을 코드로 만들 방법을 찾기 위함)."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from pathlib import Path

import omni.kit.app
import omni.kit.commands

OUT = Path(os.environ.get("DCT_KIT_OUT", "D:/Test/experiments/omniverse_probe/out/kit"))
OUT.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    app = omni.kit.app.get_app()
    res: dict = {}
    try:
        for _ in range(20):
            await app.next_update_async()
        mgr = app.get_extension_manager()
        mgr.set_extension_enabled_immediate("omni.flowusd", True)
        for _ in range(20):
            await app.next_update_async()

        cmds = omni.kit.commands.get_commands()
        names = sorted(k for k in cmds.keys() if "flow" in str(k).lower())
        res["flow_commands"] = names
        details = {}
        for n in names[:25]:
            try:
                cls = omni.kit.commands.get_command_class(n)
                sig = str(inspect.signature(cls.__init__))
                details[n] = sig
            except Exception as exc:  # noqa: BLE001
                details[n] = f"signature error: {exc}"
        res["flow_command_signatures"] = details

        try:
            import omni.flowusd as fu

            res["omni.flowusd_attrs"] = [a for a in dir(fu) if not a.startswith("_")][:80]
        except Exception as exc:  # noqa: BLE001
            res["omni.flowusd_import_error"] = f"{type(exc).__name__}: {exc}"

        # 관련 Python 모듈 이름 찾기
        import sys

        res["flow_modules"] = sorted(m for m in sys.modules if "flow" in m.lower())[:60]
    except Exception as exc:  # noqa: BLE001
        import traceback

        res["fatal"] = traceback.format_exc()
    finally:
        (OUT / "kit_explore_flow.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_explore] done", flush=True)
        app.post_quit()


asyncio.ensure_future(main())
