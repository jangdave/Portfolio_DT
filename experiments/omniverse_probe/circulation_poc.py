"""순환의 시작(공급)과 끝(회수), 공조기(CRAC)별 공기 순환을 보여 줄 수 있는지 검토하는 시험.

두 가지 흐름을 비교한다.
  A) 현재 모델의 흐름: 영역별로 정해 둔 속도 (thermal_poc.py). 순환이 닫히는지 본다.
  B) 질량이 보존되는 흐름(퍼텐셜 흐름): 공급구는 공기를 내보내는 원천, 랙 앞면은 빨아들이는 곳, 랙 뒷면은 내보내는 곳,
     회수구는 빨아들이는 곳으로 두고 ∇·u = s, u = ∇φ를 푼다(소용돌이 없는 흐름). 공급 → 랙 → 회수가 이어지는지 본다.
시나리오: 정상(CRAC 2기 모두 작동)과 CRAC_02 정지. 유선(공기 입자의 경로)을 공급구에서 출발시켜 끝나는 곳을 센다.

주의: B는 공기의 점성, 난류, 부력을 계산하지 않는 단순한 모델이다. 순환의 '구조'를 보여 주는 용도이며 공학적 해석이 아니다.
사용 (이 폴더에서): uv run --python 3.13 python circulation_poc.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.ndimage as ndi
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image, ImageDraw

import thermal_poc as tp

OUT = Path(__file__).resolve().parent / "out" / "circulation"
OUT.mkdir(parents=True, exist_ok=True)
DX = 0.1
V_RACK = 0.8        # 랙 안 공기 속도 (m/s), thermal_poc.py와 같다
RACK_A, RACK_B = 1, 2


def cells(lo_cm: float, hi_cm: float) -> tuple[int, int]:
    return int(round(lo_cm / 100.0 / DX)), int(round(hi_cm / 100.0 / DX))


class Layout:
    """USD 장면에서 읽은 랙과 CRAC로 셀 종류와 원천(공급, 회수, 랙 앞뒤)을 만든다."""

    def __init__(self, scene: dict):
        self.nx, self.ny, self.nz = (int(round(c / 100.0 / DX)) for c in tp.HALL_CM)
        shape = (self.nx, self.ny, self.nz)
        self.rack = np.zeros(shape, dtype=np.int8)          # 0 없음, 1 앞면이 +y쪽인 랙(줄 A), 2 앞면이 -y쪽인 랙(줄 B)
        self.solid = np.zeros(shape, dtype=bool)            # CRAC 몸체
        self.supply = np.full(shape, -1, dtype=np.int8)     # 공급 영역의 CRAC 번호
        self.ret = np.full(shape, -1, dtype=np.int8)        # 회수 영역의 CRAC 번호
        self.intake = np.zeros(shape, dtype=bool)           # 랙 앞면 바로 바깥 셀(빨아들임)
        self.exhaust = np.zeros(shape, dtype=bool)          # 랙 뒷면 바로 바깥 셀(내보냄)
        self.rack_flux = []                                 # 랙 하나의 통과 유량 (m^3/s)
        self.rack_boxes = []                                # 랙마다 (줄 종류, x 시작, x 끝, y 시작, y 끝) 셀 범위
        for r in scene["racks"]:
            (x0, y0, z0), (x1, y1, z1) = r["min"], r["max"]
            xs, xe = cells(x0, x1); ys, ye = cells(y0, y1); zs, ze = cells(z0, z1)
            kind = RACK_A if (y0 + y1) / 2 < 300.0 else RACK_B
            self.rack[xs:xe, ys:ye, zs:ze] = kind
            self.rack_boxes.append((kind, xs, xe, ys, ye))
            if kind == RACK_A:      # 앞면 y=y1(+y쪽), 뒷면 y=y0
                self.intake[xs:xe, ye:ye + 1, zs:ze] = True
                self.exhaust[xs:xe, ys - 1:ys, zs:ze] = True
            else:                   # 앞면 y=y0(-y쪽), 뒷면 y=y1
                self.intake[xs:xe, ys - 1:ys, zs:ze] = True
                self.exhaust[xs:xe, ye:ye + 1, zs:ze] = True
            self.rack_flux.append(V_RACK * ((x1 - x0) / 100.0) * ((z1 - z0) / 100.0))
        self.crac_x = []
        for idx, c in enumerate(scene["cracs"]):
            (x0, y0, z0), (x1, y1, z1) = c["min"], c["max"]
            xs, xe = cells(x0, x1); ys, ye = cells(y0, y1); zs, ze = cells(z0, z1)
            self.solid[xs:xe, ys:ye, zs:ze] = True
            west = (x0 + x1) / 2 < tp.HALL_CM[0] / 2
            fx0, fx1 = (x1, x1 + 40.0) if west else (x0 - 40.0, x0)
            a, b = cells(fx0, fx1)
            self.supply[a:b, ys:ye, 0:int(round(0.8 / DX))] = idx
            a, b = cells(x0, x1)
            self.ret[a:b, ys:ye, ze:ze + int(round(0.6 / DX))] = idx
            self.crac_x.append((x0 + x1) / 2)
        self.fluid = ~(self.solid | (self.rack > 0))
        # 랙 앞뒤 원천이 CRAC 몸체나 랙 안에 걸치지 않도록 제한
        self.intake &= self.fluid
        self.exhaust &= self.fluid


def source_field(lay: Layout, fan: list[float], q_supply: float) -> np.ndarray:
    """셀마다 원천의 세기(1/s). 양수는 내보냄, 음수는 빨아들임. 총합은 0이 되도록 맞춘다."""
    s = np.zeros((lay.nx, lay.ny, lay.nz), dtype=np.float64)
    vol = DX ** 3
    for idx, f in enumerate(fan):
        q = f * q_supply
        sup = lay.supply == idx
        ret = lay.ret == idx
        if q > 0 and sup.any() and ret.any():
            s[sup] += q / (sup.sum() * vol)
            s[ret] -= q / (ret.sum() * vol)
    rack_q = float(np.mean(lay.rack_flux))
    nin, nex = lay.intake.sum(), lay.exhaust.sum()
    q_total = rack_q * len(lay.rack_flux)
    s[lay.intake] -= q_total / (nin * vol)
    s[lay.exhaust] += q_total / (nex * vol)
    return s


def solve_potential(lay: Layout, s: np.ndarray) -> np.ndarray:
    """∇²φ = s 를 푼다. 벽과 장애물(랙 안, CRAC 몸체)에는 흐름이 드나들지 않는다. u = ∇φ를 셀 중심 속도로 돌려준다."""
    fluid = lay.fluid
    idx = -np.ones(fluid.shape, dtype=np.int64)
    idx[fluid] = np.arange(fluid.sum())
    n = int(fluid.sum())
    rows, cols, vals = [], [], []
    diag = np.zeros(n)
    for axis in range(3):
        for sign in (-1, 1):
            nb = np.roll(fluid, -sign, axis=axis)
            # 가장자리를 넘어간 이웃은 유체가 아니다(벽)
            edge = [slice(None)] * 3
            edge[axis] = slice(-1, None) if sign == 1 else slice(0, 1)
            nb[tuple(edge)] = False
            both = fluid & nb
            ii = idx[both]
            shifted = np.roll(idx, -sign, axis=axis)
            jj = shifted[both]
            rows.append(ii); cols.append(jj); vals.append(np.ones(ii.size))
            np.add.at(diag, ii, -1.0)
    A = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    A = A + sp.diags(diag)
    b = s[fluid] * DX * DX
    # 합이 0이어야 풀린다. 한 칸의 φ를 0으로 고정해서 특이성을 없앤다.
    b = b - b.mean()
    A = A.tolil()
    A[0, :] = 0
    A[0, 0] = 1.0
    b[0] = 0.0
    phi_vec = spla.spsolve(A.tocsc(), b)
    phi = np.zeros(fluid.shape)
    phi[fluid] = phi_vec
    # 속도 = φ의 기울기. 장애물 쪽 이웃은 법선 방향 기울기가 0이 되도록 자기 값을 쓴다.
    u = np.zeros(fluid.shape + (3,), dtype=np.float32)
    for axis in range(3):
        plus = np.roll(phi, -1, axis=axis); minus = np.roll(phi, 1, axis=axis)
        f_plus = np.roll(fluid, -1, axis=axis); f_minus = np.roll(fluid, 1, axis=axis)
        last = [slice(None)] * 3; last[axis] = slice(-1, None); f_plus[tuple(last)] = False
        first = [slice(None)] * 3; first[axis] = slice(0, 1); f_minus[tuple(first)] = False
        plus = np.where(f_plus, plus, phi); minus = np.where(f_minus, minus, phi)
        u[..., axis] = ((plus - minus) / (2 * DX)).astype(np.float32)
    u[~fluid] = 0.0
    # 랙 안은 정해 둔 통과 속도: 줄 A는 -y 방향, 줄 B는 +y 방향 (앞면에서 뒷면으로)
    u[lay.rack == RACK_A] = (0.0, -V_RACK, 0.0)
    u[lay.rack == RACK_B] = (0.0, V_RACK, 0.0)
    div = np.zeros(fluid.shape)
    for axis in range(3):
        div += np.gradient(u[..., axis], DX, axis=axis)
    return u, float(np.abs(div[fluid & ~lay.intake & ~lay.exhaust & (lay.supply < 0) & (lay.ret < 0)]).mean())


def prescribed_velocity(lay: Layout, fan: list[float]) -> np.ndarray:
    """A) 현재 모델의 정해 둔 흐름을 같은 격자에 만든다 (thermal_poc.py의 규칙)."""
    hall = tp.Hall(tp.read_scene(tp.OUT / "poc_hall.usda"))
    for i, f in enumerate(fan):
        hall.set_fan(i, f)
    import export_direction_fields as ef
    return ef.velocity(hall)


def trace(u: np.ndarray, lay: Layout, seeds: np.ndarray, direction: float = 1.0, max_steps: int = 4000, stop=None):
    """유선을 따라간다(2차 룬게-쿠타). seeds: (N,3) 셀 좌표. direction=-1이면 거꾸로 거슬러 올라간다."""
    n = len(seeds)
    pos = seeds.astype(np.float64).copy()
    alive = np.ones(n, dtype=bool)
    end_kind = np.full(n, "max_steps", dtype=object)
    end_id = np.full(n, -1, dtype=np.int64)
    paths = [[tuple(p)] for p in pos]
    shape = np.array(u.shape[:3])

    def vel(p):
        coords = p.T
        return np.stack([ndi.map_coordinates(u[..., a], coords, order=1, mode="nearest") for a in range(3)], axis=1)

    for step in range(max_steps):
        if not alive.any():
            break
        idx = np.where(alive)[0]
        p = pos[idx]
        v1 = vel(p) * direction
        sp1 = np.linalg.norm(v1, axis=1)
        dt = np.where(sp1 > 1e-4, 0.4 * 1.0 / np.maximum(sp1 / DX, 1e-6), 0.0)  # 한 단계에 약 0.4칸 이동
        dt = np.minimum(dt, 0.4 / np.maximum(sp1 / DX, 1e-6))
        mid = p + 0.5 * dt[:, None] * (v1 / DX)
        v2 = vel(mid) * direction
        newp = p + dt[:, None] * (v2 / DX)
        stuck = np.linalg.norm(v2, axis=1) < 1e-4
        outside = np.any(newp < 0, axis=1) | np.any(newp > shape - 1, axis=1)
        newp = np.clip(newp, 0, shape - 1)
        pos[idx] = newp
        ij = np.clip(np.round(newp).astype(int), 0, shape - 1)
        for k, gi in enumerate(idx):
            if step % 6 == 0:
                paths[gi].append(tuple(newp[k]))
        done_here = np.zeros(len(idx), dtype=bool)
        if stop is not None:
            kind, ident = stop(ij)
            hit = kind != ""
            for k in np.where(hit)[0]:
                end_kind[idx[k]] = kind[k]; end_id[idx[k]] = ident[k]
            done_here |= hit
        for k in np.where(stuck & ~done_here)[0]:
            end_kind[idx[k]] = "stuck"
        for k in np.where(outside & ~done_here)[0]:
            end_kind[idx[k]] = "outside"
        alive[idx[done_here | stuck | outside]] = False
    return paths, end_kind, end_id


def forward_stop(lay: Layout):
    def f(ij):
        kind = np.full(len(ij), "", dtype=object); ident = np.full(len(ij), -1, dtype=np.int64)
        r = lay.ret[ij[:, 0], ij[:, 1], ij[:, 2]]
        m = r >= 0
        kind[m] = "return"; ident[m] = r[m]
        return kind, ident
    return f


def backward_stop(lay: Layout):
    def f(ij):
        kind = np.full(len(ij), "", dtype=object); ident = np.full(len(ij), -1, dtype=np.int64)
        s = lay.supply[ij[:, 0], ij[:, 1], ij[:, 2]]
        m = s >= 0
        kind[m] = "supply"; ident[m] = s[m]
        e = lay.exhaust[ij[:, 0], ij[:, 1], ij[:, 2]] & ~m
        kind[e] = "recirculation"
        return kind, ident
    return f


def supply_seeds(lay: Layout, idx: int, n_y: int = 5, n_z: int = 4) -> np.ndarray:
    xs = np.where((lay.supply == idx).any(axis=(1, 2)))[0]
    ys = np.where((lay.supply == idx).any(axis=(0, 2)))[0]
    x_face = xs.min() if lay.crac_x[idx] > tp.HALL_CM[0] / 2 else xs.max()
    # 공급 영역의 가운데 부근에서 출발시킨다
    x_seed = (xs.min() + xs.max()) / 2.0
    out = []
    for y in np.linspace(ys.min() + 1, ys.max() - 1, n_y):
        for z in np.linspace(1, int(round(0.7 / DX)), n_z):
            out.append((x_seed, y, z))
    return np.array(out)


def intake_seeds(lay: Layout, z_cm=(60, 120, 180)) -> tuple[np.ndarray, list[str]]:
    seeds, labels = [], []
    # 랙마다 시드를 만든다. 앞면에서 3칸(30cm) 떨어진 통로 쪽에 둔다(앞면 바로 옆 칸의 경계 영향을 피함).
    for rid, (kind, xs, xe, ys, ye) in enumerate(lay.rack_boxes, start=1):
        xm = (xs + xe - 1) / 2.0
        y_front = ye - 1 + 3.0 if kind == RACK_A else ys - 3.0
        for z in z_cm:
            seeds.append((xm, y_front, z / 100.0 / DX)); labels.append(f"rack{rid}")
    return np.array(seeds), labels


def draw(paths, kinds, ends, lay: Layout, view: str, title: str, path: Path, colors: dict, scale: int = 9):
    """위에서 본 그림(top) 또는 옆에서 본 그림(side). 유선 색은 출발한 CRAC, 시작은 동그라미, 끝은 네모."""
    if view == "top":
        W, H = lay.nx * scale, lay.ny * scale
        proj = lambda p: (p[0] * scale + scale / 2, H - (p[1] * scale + scale / 2))
    else:
        W, H = lay.nx * scale, lay.nz * scale
        proj = lambda p: (p[0] * scale + scale / 2, H - (p[2] * scale + scale / 2))
    im = Image.new("RGB", (W, H + 22), (18, 18, 22))
    d = ImageDraw.Draw(im)
    # 장비 윤곽
    def box_cells(mask, color):
        if view == "top":
            m2 = mask.any(axis=2)
        else:
            m2 = mask.any(axis=1)
        for (a, b) in np.argwhere(m2):
            x0 = a * scale; y0 = (H - (b + 1) * scale)
            d.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=color)
    box_cells(lay.rack > 0, (70, 70, 80))
    box_cells(lay.solid, (40, 70, 110))
    for p, k, e in zip(paths, kinds, ends):
        col = colors.get(k, (200, 200, 200))
        pts = [proj(q) for q in p]
        if len(pts) > 1:
            d.line(pts, fill=col, width=1)
        d.ellipse([pts[0][0] - 3, pts[0][1] - 3, pts[0][0] + 3, pts[0][1] + 3], outline=(255, 255, 255))
        end_col = (255, 80, 80) if e == "return" else (255, 255, 0)
        d.rectangle([pts[-1][0] - 3, pts[-1][1] - 3, pts[-1][0] + 3, pts[-1][1] + 3], outline=end_col)
    d.text((6, H + 4), title, fill=(255, 255, 255))
    im.save(path)


def evaluate(lay: Layout, u: np.ndarray, label: str, draw_images: bool, fan: list[float]) -> dict:
    colors = {0: (80, 170, 255), 1: (255, 170, 60)}
    res = {"label": label, "velocity_max_ms": round(float(np.linalg.norm(u, axis=-1).max()), 2)}
    # 1) 공급구에서 출발 -> 어디서 끝나는가
    all_paths, all_kinds, all_ends, per_crac = [], [], [], {}
    for idx, f in enumerate(fan):
        if f <= 0:
            per_crac[f"CRAC_{idx + 1:02d}"] = {"seeds": 0, "note": "정지"}
            continue
        seeds = supply_seeds(lay, idx)
        paths, ek, ei = trace(u, lay, seeds, 1.0, stop=forward_stop(lay))
        reached = int(sum(1 for k in ek if k == "return"))
        own = int(sum(1 for k, i in zip(ek, ei) if k == "return" and i == idx))
        per_crac[f"CRAC_{idx + 1:02d}"] = {
            "seeds": len(seeds), "reached_return": reached, "reached_own_return": own,
            "end_kinds": {k: int(sum(1 for x in ek if x == k)) for k in set(ek)},
        }
        all_paths += paths; all_kinds += [idx] * len(paths); all_ends += list(ek)
    res["from_supply"] = per_crac
    # 2) 랙 앞면에서 거꾸로 거슬러 올라가 공기가 어디서 왔는지 (담당 CRAC)
    seeds, labels = intake_seeds(lay)
    _, ek, ei = trace(u, lay, seeds, -1.0, stop=backward_stop(lay))
    origin = {"CRAC_01": 0, "CRAC_02": 0, "recirculation(다른 랙 뒷면)": 0, "미확인": 0}
    for k, i in zip(ek, ei):
        if k == "supply":
            origin[f"CRAC_{i + 1:02d}"] += 1
        elif k == "recirculation":
            origin["recirculation(다른 랙 뒷면)"] += 1
        else:
            origin["미확인"] += 1
    total = max(1, len(seeds))
    res["rack_intake_origin_percent"] = {k: round(100.0 * v / total, 1) for k, v in origin.items()}
    # 담당 영역: 줄 A/B 랙을 서쪽(x<4m)과 동쪽(x>=4m)으로 나눠서 어느 CRAC가 담당하는지
    xs = seeds[:, 0] * DX
    for name, mask in (("west_racks", xs < 4.0), ("east_racks", xs >= 4.0)):
        o = {"CRAC_01": 0, "CRAC_02": 0, "recirculation": 0, "unknown": 0}
        for k, i, m in zip(ek, ei, mask):
            if not m:
                continue
            o["CRAC_%02d" % (i + 1) if k == "supply" else ("recirculation" if k == "recirculation" else "unknown")] += 1
        n = max(1, int(mask.sum()))
        res[f"{name}_intake_origin_percent"] = {k: round(100.0 * v / n, 1) for k, v in o.items()}
    if draw_images:
        for view in ("top", "side"):
            draw(all_paths, all_kinds, all_ends, lay, view, f"{label} / {view} (circle=start, square=end, yellow=not closed, red=return)", OUT / f"streamlines_{label}_{view}.png", colors)
    return res


def main() -> None:
    scene = tp.read_scene(tp.OUT / "poc_hall.usda")
    lay = Layout(scene)
    q_supply = float(np.mean(lay.rack_flux)) * len(lay.rack_flux) / 2.0  # CRAC 한 대가 랙 전체 유량의 절반을 공급
    results = {"grid": [lay.nx, lay.ny, lay.nz], "q_supply_m3s_per_crac": round(q_supply, 2), "rack_flux_m3s_each": round(float(np.mean(lay.rack_flux)), 2), "scenarios": []}
    for name, fan in (("normal", [1.0, 1.0]), ("crac02_off", [1.0, 0.0])):
        # A) 현재 모델의 정해 둔 흐름
        ua = prescribed_velocity(lay, fan)
        ra = evaluate(lay, ua, f"A_{name}", True, fan)
        ra["model"] = "A 정해 둔 흐름(현재)"
        # B) 질량 보존 흐름
        s = source_field(lay, fan, q_supply)
        ub, div_err = solve_potential(lay, s)
        rb = evaluate(lay, ub, f"B_{name}", True, fan)
        rb["model"] = "B 질량 보존 흐름(퍼텐셜)"
        rb["mean_abs_divergence_in_free_cells_per_s"] = round(div_err, 4)
        results["scenarios"] += [ra, rb]
        np.save(OUT / f"u_B_{name}.npy", ub)
    (OUT / "circulation_stats.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
