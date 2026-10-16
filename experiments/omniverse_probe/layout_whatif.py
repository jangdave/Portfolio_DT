"""랙 배치를 바꿔 다시 계산하는 흐름 시험(사용자 요구: Unreal에서 랙을 옮기고 바뀐 배치로 시뮬레이션을 다시 돌린다).

시뮬레이션은 장면 USD에서 랙 위치를 읽는다(`hall60_sim.read_hall`). 그래서 장면의 랙 prim 위치를 바꾼 USD만 있으면 된다.
이 스크립트는 그 흐름을 Unreal 없이 확인한다: ① 장면 복사본에서 랙을 옮기거나 빼고 ② 같은 시뮬레이션을 돌려 ③ 랙 입구 온도를 원래 배치와 비교한다.

사용 (이 폴더에서):
    uv run --python 3.13 python layout_whatif.py --edit '{"remove": ["Rack_05"], "move": {"Rack_15": [60, 0, 0]}}' [--duration 900] [--fail CRAC_02,CRAC_06]

- `move`: 랙 이름 -> [dx, dy, dz] (cm, 장면 좌표). `remove`: 장면에서 뺄 랙 이름. 기존 장면 파일은 바꾸지 않는다.
- 결과: out/whatif/ (편집한 장면 `scene_edit.usda`, `inlet_base.csv`, `inlet_edit.csv`, `report.json`). 시각화 목적이며 공학적 정확성을 주장하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from pxr import Gf, Usd, UsdGeom

import hall60_sim as hs

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out" / "whatif"


def shift_translate(prim: Usd.Prim, delta) -> None:
    """랙의 이동 연산(xformOp:translate)에 변위를 더한다. 랙은 이동 + 회전 연산을 쓰므로 XformCommonAPI가 받아들이지 못한다(경고만 내고 아무것도 안 한다)."""
    xf = UsdGeom.Xformable(prim)
    for op in xf.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            cur = op.Get(Usd.TimeCode.Default())
            op.Set(Gf.Vec3d(cur[0] + delta[0], cur[1] + delta[1], cur[2] + delta[2]))
            return
    raise ValueError(f"{prim.GetPath()}에 이동 연산(xformOp:translate)이 없다")


def find_overlaps(scene: Path, min_area_cm2: float = 1.0) -> list[tuple[str, str]]:
    """장면의 랙과 CRAC 중 바닥 면(x, y)이 겹치는 쌍. 겹치면 시뮬레이션에서 한 장비가 다른 장비를 덮어써서 결과가 틀린다."""
    hall = hs.read_hall(scene)
    items = [(r["name"], r["min"], r["max"]) for r in hall["racks"]] + [(c["name"], c["min"], c["max"]) for c in hall["cracs"]]
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            na, a0, a1 = items[i]
            nb, b0, b1 = items[j]
            ox = min(a1[0], b1[0]) - max(a0[0], b0[0])
            oy = min(a1[1], b1[1]) - max(a0[1], b0[1])
            if ox > 0 and oy > 0 and ox * oy >= min_area_cm2:
                out.append((na, nb))
    return out


def apply_edits(src: Path, dst: Path, edits: dict) -> dict:
    """장면 복사본에 랙 이동과 제거를 적용한다. 참조(에셋)를 풀어 한 파일로 저장하므로 어디에 두어도 열린다."""
    stage = Usd.Stage.Open(str(src))
    by_name: dict[str, Usd.Prim] = {}
    for prim in stage.Traverse():
        at = prim.GetAttribute("dct:assetType")
        if at and at.Get() == "rack":
            by_name[prim.GetName()] = prim
    unknown = [n for n in list(edits.get("move", {})) + list(edits.get("remove", [])) if n not in by_name]
    if unknown:
        raise KeyError(f"장면에 없는 랙: {unknown}")
    both = set(edits.get("move", {})) & set(edits.get("remove", []))
    if both:
        raise ValueError(f"옮기면서 동시에 빼는 랙: {sorted(both)}")
    for name, delta in edits.get("move", {}).items():
        if len(delta) != 3:
            raise ValueError(f"move 값은 [dx, dy, dz]여야 한다: {name}")
        shift_translate(by_name[name], delta)
    for name in edits.get("remove", []):
        by_name[name].SetActive(False)
    dst.parent.mkdir(parents=True, exist_ok=True)
    stage.Flatten().Export(str(dst))
    clashes = find_overlaps(dst)
    if clashes:
        dst.unlink(missing_ok=True)
        raise ValueError("편집한 배치에서 장비가 겹친다(옮기는 자리가 비어 있어야 한다): " + ", ".join(f"{a}와 {b}" for a, b in clashes[:6]))
    return {"moved": len(edits.get("move", {})), "removed": len(edits.get("remove", [])), "racks_in_scene": len(by_name)}


def run_scene(scene: Path, out: Path, duration: int, fail: str, advection: str) -> dict[str, float]:
    """hall60_sim을 이 장면으로 돌리고, 마지막 프레임에서 랙 입구 센서 위치의 온도를 읽는다. {랙 이름: 온도}"""
    argv = sys.argv
    old_out = hs.OUT
    hs.OUT = out
    sys.argv = ["hall60_sim.py", "--scene", str(scene), "--duration", str(duration), "--fail", fail, "--every", str(duration), "--advection", advection]
    try:
        hs.main()
    finally:
        sys.argv, hs.OUT = argv, old_out
    hall = hs.read_hall(scene)
    T = np.load(out / "frames" / f"T_{duration:04d}.npy")
    res: dict[str, float] = {}
    for a in hall["anchors"]:
        if a["metric"] != "temp_in":
            continue
        i, j, k = (int(np.clip(np.floor(a["pos_cm"][n] / 100.0 / hs.DX), 0, T.shape[n] - 1)) for n in range(3))
        res[a["equipment"]] = float(T[i, j, k])
    return res


def write_csv(path: Path, data: dict[str, float]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rack", "temp_c"])
        for k in sorted(data):
            w.writerow([k, f"{data[k]:.3f}"])


def main() -> None:
    ap = argparse.ArgumentParser(description="랙 배치를 바꿔 다시 계산하고 원래 배치와 비교")
    ap.add_argument("--scene", type=Path, default=HERE.parents[1] / "usd" / "scenes" / "hall01.usda")
    ap.add_argument("--edit", required=True, help='JSON. 예: {"remove": ["Rack_05"], "move": {"Rack_15": [60, 0, 0]}}')
    ap.add_argument("--duration", type=int, default=900)
    ap.add_argument("--fail", default="CRAC_02,CRAC_06")
    ap.add_argument("--advection", choices=["linear", "maccormack"], default="maccormack")
    ap.add_argument("--min-delta", type=float, default=0.3, help="이 값(도) 이상 달라진 랙만 표에 낸다")
    args = ap.parse_args()
    edits = json.loads(args.edit)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scene_edit = OUT_DIR / "scene_edit.usda"
    info = apply_edits(args.scene, scene_edit, edits)
    base = run_scene(args.scene, OUT_DIR / "base", args.duration, args.fail, args.advection)
    edit = run_scene(scene_edit, OUT_DIR / "edit", args.duration, args.fail, args.advection)
    write_csv(OUT_DIR / "inlet_base.csv", base)
    write_csv(OUT_DIR / "inlet_edit.csv", edit)
    common = sorted(set(base) & set(edit))
    delta = {k: edit[k] - base[k] for k in common}
    changed = {k: v for k, v in delta.items() if abs(v) >= args.min_delta}
    report = {
        "edits": edits, **info, "racks_base": len(base), "racks_edit": len(edit),
        "mean_base": float(np.mean(list(base.values()))), "mean_edit": float(np.mean(list(edit.values()))),
        "max_base": max(base.values()), "max_edit": max(edit.values()),
        "changed_racks": {k: round(v, 2) for k, v in sorted(changed.items(), key=lambda kv: -abs(kv[1]))},
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"랙 {len(base)}기 -> {len(edit)}기 (이동 {info['moved']}, 제거 {info['removed']})")
    print(f"입구 평균 {report['mean_base']:.2f} -> {report['mean_edit']:.2f}도, 최대 {report['max_base']:.2f} -> {report['max_edit']:.2f}도")
    print(f"{args.min_delta}도 이상 달라진 랙 {len(changed)}기:")
    for k, v in list(report["changed_racks"].items())[:12]:
        print(f"  {k}: {v:+.2f}도")


if __name__ == "__main__":
    main()
