"""R2 실증: Kit 안에서 Flow로 열 플룸(불) 시뮬레이션을 만들고, 화면으로 확인한 뒤 온도·속도 채널을 OpenVDB로 내보낸다.

결과: out/kit/flow_*.png(시간대별 화면), out/kit/flow_vdb/*.vdb, out/kit/kit_flow_sim_result.json
주의: 모양과 값은 Flow의 "Fire" 프리셋 기본값이며, 우리 데이터센터 열 모델이 아니다. 화면과 내보내기 경로 확인이 목적이다.
Flow 프리셋은 미터 단위 장면을 기준으로 만들어져 있어, 이 실험의 장면 단위는 미터(metersPerUnit=1)로 한다.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from pathlib import Path

import omni.kit.app
import omni.kit.commands
import omni.timeline
import omni.usd
from pxr import Gf, Sdf, UsdGeom

OUT = Path(os.environ.get("DCT_KIT_OUT", "D:/Test/experiments/omniverse_probe/out/kit"))
EXPORT = os.environ.get("DCT_EXPORT", "1") == "1"   # 0이면 VDB 내보내기를 끈다 (FPS 비교용)
FRAMES = int(os.environ.get("DCT_FRAMES", "500"))
SNAPS = [int(x) for x in os.environ.get("DCT_SNAPS", "90,240,480").split(",")]
TAG = os.environ.get("DCT_TAG", "exp")
EYE = [float(x) for x in os.environ.get("DCT_EYE", "3.2,-3.2,2.2").split(",")]
TARGET = [float(x) for x in os.environ.get("DCT_TARGET", "0,0,1.2").split(",")]
VDB_DIR = OUT / "flow_vdb"
OUT.mkdir(parents=True, exist_ok=True)
VDB_DIR.mkdir(parents=True, exist_ok=True)
for old in list(VDB_DIR.glob("*")) + list(OUT.glob(f"flow_{TAG}_t*.png")):
    try:
        old.unlink()
    except OSError:
        pass

res: dict = {"steps": {}}


def log(name, ok, detail=None):
    res["steps"][name] = {"ok": ok, "detail": detail}
    print(f"[kit_flow_sim] {name}: {'OK' if ok else 'FAIL'} {detail if detail is not None else ''}", flush=True)


def vdb_files():
    return sorted(p for p in VDB_DIR.rglob("*") if p.is_file())


async def snap(app, viewport, name: str) -> dict:
    from omni.kit.viewport.utility import capture_viewport_to_file

    png = OUT / name
    cap = capture_viewport_to_file(viewport, str(png))
    await cap.wait_for_result(completion_frames=20)
    for _ in range(5):
        await app.next_update_async()
    return {"file": name, "bytes": png.stat().st_size if png.exists() else 0}


async def main() -> None:
    app = omni.kit.app.get_app()
    try:
        for _ in range(30):
            await app.next_update_async()
        mgr = app.get_extension_manager()
        mgr.set_extension_enabled_immediate("omni.flowusd", True)
        for _ in range(30):
            await app.next_update_async()

        ctx = omni.usd.get_context()
        await ctx.new_stage_async()
        stage = ctx.get_stage()
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)  # Flow 프리셋은 미터 단위 기준
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        world = UsdGeom.Xform.Define(stage, "/World")
        stage.SetDefaultPrim(world.GetPrim())

        # 바닥(크기 확인용)과 열원 위치
        floor = UsdGeom.Cube.Define(stage, "/World/Floor")
        floor.GetSizeAttr().Set(1.0)
        fx = UsdGeom.Xformable(floor)
        fx.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.01))
        fx.AddScaleOp().Set(Gf.Vec3f(6.0, 6.0, 0.02))
        heat = UsdGeom.Xform.Define(stage, "/World/Heat")
        UsdGeom.Xformable(heat).AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.3))

        # 카메라: 열원을 비스듬히 위에서 본다 (3 m 거리)
        cam = UsdGeom.Camera.Define(stage, "/World/Cam")
        eye, target = Gf.Vec3d(*EYE), Gf.Vec3d(*TARGET)
        m = Gf.Matrix4d().SetLookAt(eye, target, Gf.Vec3d(0, 0, 1)).GetInverse()
        UsdGeom.Xformable(cam).AddTransformOp().Set(m)
        cam.GetFocalLengthAttr().Set(24.0)
        for _ in range(10):
            await app.next_update_async()

        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        viewport.camera_path = "/World/Cam"

        omni.kit.commands.execute("FlowCreatePresets", preset_name="Fire", paths=["/World/Heat"])
        for _ in range(30):
            await app.next_update_async()
        created = [(str(p.GetPath()), p.GetTypeName()) for p in stage.Traverse() if "Flow" in str(p.GetTypeName())]
        log("create_preset", len(created) > 0, f"{len(created)}개 Flow prim")

        # 내보내기 설정
        export_prim = next((stage.GetPrimAtPath(p) for p, t in created if t == "FlowSparseNanoVdbExportParams"), None)
        if export_prim is not None and EXPORT:
            def setv(name, value):
                export_prim.GetAttribute(name).Set(value)
            for k in ("enabled", "temperatureEnabled", "velocityEnabled", "smokeEnabled", "readbackEnabled", "readbackOpenVDB"):
                setv(k, True)
            setv("readbackClearOnStart", False)
            setv("readbackClearOnStop", False)
            export_prim.GetAttribute("readbackDirectory").Set(Sdf.AssetPath(VDB_DIR.as_posix()))
            log("configure_export", True, str(export_prim.GetPath()))

        # 시뮬레이션: 타임라인을 재생하면서 시간대별로 화면 저장
        tl = omni.timeline.get_timeline_interface()
        tl.set_end_time(30.0)
        tl.play()
        shots = []
        t0 = time.perf_counter()
        snaps_at = {n: f"flow_{TAG}_t{n:03d}.png" for n in SNAPS}
        fps_marks = []
        t_mark = time.perf_counter()
        for i in range(FRAMES):
            await app.next_update_async()
            if i in snaps_at:
                shots.append(await snap(app, viewport, snaps_at[i]))
            if (i + 1) % 100 == 0:
                now = time.perf_counter()
                fps_marks.append({"frames": i + 1, "fps_last_100": round(100 / (now - t_mark), 1)})
                t_mark = now
        res["fps_by_100_frames"] = fps_marks
        res["frames"] = FRAMES
        res["export_enabled"] = EXPORT
        res["wall_s_for_frames"] = round(time.perf_counter() - t0, 1)
        res["avg_fps"] = round(FRAMES / res["wall_s_for_frames"], 1)
        res["timeline_time_s_at_end"] = round(tl.get_current_time(), 2)
        tl.pause()
        res["screenshots"] = shots
        log("screenshots", all(s["bytes"] > 1000 for s in shots), shots)

        files = vdb_files()
        res["vdb_files_total"] = len(files)
        res["vdb_files_sample"] = [
            {"name": f.name, "bytes": f.stat().st_size, "openvdb_magic": f.read_bytes()[:4] == bytes([0x20, 0x42, 0x44, 0x56])}
            for f in files[:12]
        ]
        res["vdb_total_mb"] = round(sum(f.stat().st_size for f in files) / 1e6, 2)
        log("export", (len(files) > 0) == EXPORT, {"files": len(files), "total_mb": res["vdb_total_mb"], "sample": res["vdb_files_sample"][:3]})
    except Exception:  # noqa: BLE001
        res["fatal"] = traceback.format_exc()
        print(res["fatal"], flush=True)
    finally:
        (OUT / "kit_flow_sim_result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[kit_flow_sim] done", flush=True)
        app.post_quit()


asyncio.ensure_future(main())
