"""Kit 확장 레지스트리 전체에서 시뮬레이션 관련 확장이 무엇이 있는지 조회한다.

레지스트리 조회 호출을 하나씩 시험하고, 각 호출이 무엇을 돌려주는지 결과에 남긴다.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import traceback
from pathlib import Path

import omni.kit.app

OUT = Path(os.environ.get("DCT_KIT_OUT", "D:/Test/experiments/omniverse_probe/out/kit"))
OUT.mkdir(parents=True, exist_ok=True)
KEYWORDS = [
    "flow", "fluid", "cfd", "cae", "thermal", "heat", "fire", "smoke", "temperature", "combust", "fem", "warp",
    "particle", "flex", "deformable", "softbody", "cloth", "rope", "vehicle", "ragdoll", "physx", "physics", "newton",
    "isaac", "robot", "replicator", "sensor", "lidar", "radar", "simready", "weather", "wind", "vdb", "datacenter", "dsx",
]


def describe(x):
    t = type(x).__name__
    try:
        n = len(x)
    except Exception:  # noqa: BLE001
        n = None
    return {"type": t, "len": n}


def names_from(obj) -> set[str]:
    """어떤 모양이든 확장 이름 문자열을 최대한 꺼낸다."""
    out: set[str] = set()

    def walk(o, depth=0):
        if depth > 3 or o is None:
            return
        if isinstance(o, str):
            if o.startswith(("omni.", "isaacsim.", "carb.", "usd.", "omni_")):
                out.add(o.split("-")[0])
        elif isinstance(o, dict):
            if "name" in o and isinstance(o["name"], str):
                out.add(o["name"])
            for k, v in o.items():
                if isinstance(k, str) and k.startswith(("omni.", "isaacsim.")):
                    out.add(k.split("-")[0])
                walk(v, depth + 1)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v, depth + 1)
        else:
            nm = getattr(o, "name", None)
            if isinstance(nm, str):
                out.add(nm)

    walk(obj)
    return out


async def main() -> None:
    app = omni.kit.app.get_app()
    res: dict = {"calls": {}}
    try:
        for _ in range(30):
            await app.next_update_async()
        mgr = app.get_extension_manager()
        names: set[str] = set()

        async def try_call(label, fn, *args):
            try:
                out = fn(*args)
                if inspect.isawaitable(out):
                    out = await out
                res["calls"][label] = describe(out)
                got = names_from(out)
                res["calls"][label]["names_found"] = len(got)
                names.update(got)
                return out
            except Exception as exc:  # noqa: BLE001
                res["calls"][label] = {"error": f"{type(exc).__name__}: {str(exc)[:150]}"}

        await try_call("refresh_registry", mgr.refresh_registry)
        for _ in range(60):
            await app.next_update_async()
        await try_call("sync_registry", mgr.sync_registry)
        for _ in range(60):
            await app.next_update_async()
        await try_call("fetch_all_extension_packages", mgr.fetch_all_extension_packages)
        await try_call("get_registry_extension_dict", mgr.get_registry_extension_dict)
        await try_call("get_registry_extension_packages", mgr.get_registry_extension_packages)
        await try_call("fetch_extension_summaries", mgr.fetch_extension_summaries)

        res["unique_names"] = len(names)
        res["keyword_hits"] = {kw: sorted(n for n in names if kw in n.lower())[:40] for kw in KEYWORDS}
        res["sim_related_names"] = sorted(n for n in names if any(k in n.lower() for k in ("physx", "physics", "flow", "warp", "fluid", "newton", "cae", "robot", "isaac", "replicator", "sensor", "simready", "deformable", "cloth", "particle")))
    except Exception:  # noqa: BLE001
        res["fatal"] = traceback.format_exc()
        print(res["fatal"], flush=True)
    finally:
        (OUT / "kit_list_exts.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_list] done", flush=True)
        app.post_quit()


asyncio.ensure_future(main())
