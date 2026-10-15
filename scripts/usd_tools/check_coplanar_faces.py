"""USD 메시에서 같은 평면에 같은 방향으로 겹쳐 놓인 면(깜빡이는 노이즈, z-파이팅의 원인)을 찾는다.

사용 (scripts/usd_tools 폴더에서):
    uv run --python 3.13 python check_coplanar_faces.py ../../usd/assets/building.usda
    uv run --python 3.13 python check_coplanar_faces.py ../../usd/assets/building.usda --z-min 1380 --tol 0.5

- 축 정렬 직사각형 면(상자 모양)만 검사한다. 삼각형이나 원판 같은 면은 경계 상자 비교가 오탐을 만들어 제외한다. 두 면의 평면 거리가 --tol(cm) 이하이고 법선 방향이 같고 면이 겹치면 후보다.
- 법선이 서로 반대인 맞붙은 면(패널 뒷면과 벽 앞면)은 단면 렌더에서는 보이지 않으므로 후보로 세지 않는다.
- 같은 메시 안의 겹침과 다른 메시 사이의 겹침을 나눠서 보여 준다. 다른 메시 사이가 더 위험하다(재질이 다르면 색이 깜빡인다).
- 결과가 `--fail-over`보다 많으면 종료 코드 1이다(검사 자동화용).
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import numpy as np
from pxr import Usd, UsdGeom


def collect_faces(stage: Usd.Stage, z_min: float | None, min_area: float) -> list[tuple]:
    xc = UsdGeom.XformCache(Usd.TimeCode.Default())
    faces = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float64)
        pts = (np.c_[pts, np.ones(len(pts))] @ np.array(xc.GetLocalToWorldTransform(prim)))[:, :3]
        counts = np.array(mesh.GetFaceVertexCountsAttr().Get())
        idx = np.array(mesh.GetFaceVertexIndicesAttr().Get())
        name = prim.GetName().replace("_mesh", "")
        off = 0
        for c in counts:
            v = pts[idx[off:off + c]]
            off += c
            n = np.cross(v[1] - v[0], v[2] - v[0])
            ln = np.linalg.norm(n)
            if ln < 1e-9:
                continue
            n /= ln
            axis = int(np.argmax(np.abs(n)))
            if abs(n[axis]) < 0.999:
                continue
            if z_min is not None and v[:, 2].max() < z_min:
                continue
            oth = [i for i in range(3) if i != axis]
            lo, hi = v[:, oth].min(0), v[:, oth].max(0)
            bbox_area = (hi[0] - lo[0]) * (hi[1] - lo[1])
            if bbox_area < min_area:
                continue
            # 경계 상자를 거의 채우는 직사각형 면만 비교한다. 삼각형(원판 부채꼴 등)은 경계 상자가 겹쳐도 실제로는 겹치지 않아 오탐이 된다.
            a2, b2 = v[:, oth[0]], v[:, oth[1]]
            poly_area = 0.5 * abs(float(np.dot(a2, np.roll(b2, -1)) - np.dot(b2, np.roll(a2, -1))))
            if poly_area < 0.98 * bbox_area:
                continue
            faces.append((name, axis, 1 if n[axis] > 0 else -1, float(v[:, axis].mean()), lo, hi))
    return faces


def find_pairs(faces: list[tuple], tol: float, min_overlap: float) -> dict:
    """{(메시 a, 메시 b): [쌍 수, 최대 겹침 면적(cm2), 축, 평면 a, 평면 b]}"""
    buckets = collections.defaultdict(list)
    for f in faces:
        buckets[(f[1], f[2], round(f[3] / tol))].append(f)
    # 이웃 칸(경계 근처)도 같이 본다
    found: dict = {}
    for (axis, sign, k), fs in buckets.items():
        group = list(fs)
        for dk in (1,):
            group += buckets.get((axis, sign, k + dk), [])
        group = group[:2500]
        if len(group) < 2:
            continue
        lo = np.array([f[4] for f in group])
        hi = np.array([f[5] for f in group])
        for i in range(len(group)):
            ov = np.minimum(hi[i], hi[i + 1:]) - np.maximum(lo[i], lo[i + 1:])
            hit = np.where((ov[:, 0] > min_overlap) & (ov[:, 1] > min_overlap))[0]
            for h in hit:
                a, b = group[i], group[i + 1 + h]
                if abs(a[3] - b[3]) > tol:
                    continue
                key = tuple(sorted((a[0], b[0])))
                area = float(ov[h][0] * ov[h][1])
                cur = found.setdefault(key, [0, 0.0, "XYZ"[axis], round(a[3], 2), round(b[3], 2)])
                cur[0] += 1
                if area > cur[1]:
                    cur[1], cur[2], cur[3], cur[4] = area, "XYZ"[axis], round(a[3], 2), round(b[3], 2)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="같은 평면에 겹쳐 놓인 면 찾기(z-파이팅 후보)")
    ap.add_argument("file", type=Path)
    ap.add_argument("--tol", type=float, default=0.5, help="같은 평면으로 보는 거리(cm)")
    ap.add_argument("--z-min", type=float, default=None, help="이 높이(cm) 이상에 있는 면만 검사")
    ap.add_argument("--min-overlap", type=float, default=1.0, help="양쪽 방향으로 이만큼(cm) 이상 겹쳐야 센다")
    ap.add_argument("--fail-over", type=int, default=-1, help="다른 메시 사이 겹침 쌍이 이 수보다 많으면 종료 코드 1 (-1이면 항상 0)")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stage = Usd.Stage.Open(str(args.file))
    if stage is None:
        print("파일을 열 수 없다:", args.file)
        return 2
    faces = collect_faces(stage, args.z_min, min_area=1.0)
    found = find_pairs(faces, args.tol, args.min_overlap)
    cross = {k: v for k, v in found.items() if k[0] != k[1]}
    same = {k: v for k, v in found.items() if k[0] == k[1]}
    print(f"축 정렬 면 {len(faces)}개, 같은 방향 겹침: 다른 메시 사이 {sum(v[0] for v in cross.values())}쌍({len(cross)}조합), 같은 메시 안 {sum(v[0] for v in same.values())}쌍({len(same)}메시)")
    for title, d in (("다른 메시 사이", cross), ("같은 메시 안", same)):
        if not d:
            continue
        print(f"[{title}]")
        for (a, b), (n, area, ax, pa, pb) in sorted(d.items(), key=lambda kv: -kv[1][1])[: args.top]:
            print(f"  {a:16s} x {b:16s} {n:6d}쌍 최대 겹침 {area:9.0f} cm2 축 {ax} 평면 {pa} / {pb}")
    total_cross = sum(v[0] for v in cross.values())
    return 1 if args.fail_over >= 0 and total_cross > args.fail_over else 0


if __name__ == "__main__":
    sys.exit(main())
