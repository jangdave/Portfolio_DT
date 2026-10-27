"""AI 대리 모델 학습 데이터 확장: samples.json에 새 샘플 20개(s41~s60)를 덧붙인다(시드 고정, 이미 있는 40개와 보류 4개는 그대로).

실행 (experiments/omniverse_probe 폴더에서):
    uv run --python 3.13 python ../openfoam_baseline/surrogate/design_samples_v2.py

넓히는 방향(E5 한계에서 약했던 곳):
- 같은 통로 CRAC 2대 고장 6개(가장 강한 고장, 기존 8개는 같은 통로 쌍이 4종류뿐), 줄별 전력은 다르게
- 랙 제거 + 고장 6개(기존 6개, 그중 2개는 실패 또는 미수렴), 제거는 같은 줄에서 가까운 랙 1~3기
- 전력이 높은 CRAC 1대 고장 4개(줄 전력 11~14 kW)
- 팬 깊은 저하 4개(팬 0.15~0.5, 센서 생성기의 fan_fault 같은 조건)
이미 samples.json에 s41 이상이 있으면 아무것도 하지 않는다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "omniverse_probe"))
import hall60_sim as h  # noqa: E402
import layout_whatif as lw  # noqa: E402

SEED = 20261027
CRACS = [f"CRAC_{i:02d}" for i in range(1, 9)]
RACKS = [f"Rack_{i:02d}" for i in range(1, 61)]


def main() -> None:
    path = HERE / "samples.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    old = [s for s in data["samples"] if not s.get("holdout")]
    held = [s for s in data["samples"] if s.get("holdout")]
    if len(old) != 40:
        print(f"이미 확장됨(학습 샘플 {len(old)}개). 아무것도 하지 않는다.")
        return
    rs = np.random.RandomState(SEED)

    def powers(lo=6.0, hi=14.0) -> list[float]:
        return [round(float(x), 1) for x in rs.uniform(lo, hi, 6)]

    def fan_of(off=(), partial=None) -> dict:
        f = {n: 1.0 for n in CRACS}
        for n in off:
            f[n] = 0.0
        for n, v in (partial or {}).items():
            f[n] = round(float(v), 2)
        return f

    S: list[dict] = []

    def add(group, fan, remove=(), p=None):
        S.append({"id": f"s{40 + len(S) + 1:02d}_{group}", "group": group, "fan": fan, "row_power_kw": p or powers(), "remove": sorted(remove), "holdout": False})

    aisles = rs.permutation(8) % 4
    for a in aisles[:6]:
        add("same_aisle_two_off", fan_of((f"CRAC_{a + 1:02d}", f"CRAC_{a + 5:02d}")))
    for i in range(6):
        row = int(rs.randint(0, 6))
        n = int(rs.randint(1, 4))
        start = int(rs.randint(0, 10 - n + 1))
        rem = [RACKS[row * 10 + start + k] for k in range(n)]  # 같은 줄에서 이어진 랙
        if i < 2:
            a = int(rs.randint(0, 4))
            off = [f"CRAC_{a + 1:02d}", f"CRAC_{a + 5:02d}"]
        else:
            off = [CRACS[int(rs.randint(0, 8))]]
        add("remove_and_fail", fan_of(off), rem)
    for _ in range(4):
        add("one_crac_off_high_power", fan_of([CRACS[int(rs.randint(0, 8))]]), p=powers(11.0, 14.0))
    for _ in range(4):
        k = int(rs.randint(1, 4))
        idx = rs.choice(8, k, replace=False)
        add("fan_derated_deep", fan_of(partial={CRACS[i]: rs.uniform(0.15, 0.5) for i in idx}))
    assert len(S) == 20, len(S)

    base = h.ROOT / "usd" / "scenes" / "hall01.usda"
    tmp = Path(tempfile.gettempdir()) / "dct_design_check_v2.usda"
    problems = []
    for smp in S:
        scene = base
        if smp["remove"]:
            lw.apply_edits(base, tmp, {"remove": smp["remove"]})
            scene = tmp
        hall = h.read_hall(scene)
        lay = h.Layout(hall)
        fan = np.array([smp["fan"][c["name"]] for c in hall["cracs"]], dtype=np.float32)
        q, leak = h.crac_returns(lay, fan)
        exhaust = np.asarray(lay.aisle_exhaust)
        per_aisle_q = [float(sum(q[i] for i in range(lay.n_cracs) if lay.crac_aisle[i] == a)) for a in range(lay.n_aisles)]
        ok = (q.sum() > 0 and np.allclose(np.array(per_aisle_q) + leak, exhaust, atol=1e-6) and (fan > 0).any() and len(hall["racks"]) == 60 - len(smp["remove"]))
        smp["check"] = {"racks": len(hall["racks"]), "supply_m3s": round(float(q.sum()), 2), "leak_m3s": [round(float(x), 2) for x in leak],
                        "aisle_exhaust_m3s": [round(float(x), 2) for x in exhaust], "ok": bool(ok)}
        if not ok:
            problems.append(smp["id"])
    tmp.unlink(missing_ok=True)
    data["samples"] = old + S + held
    data["seed_v2"] = SEED
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"샘플 {len(S)}개 추가(총 학습 {len(old) + len(S)}개). 점검 실패: {problems or '없음'}")
    for s in S:
        off = [n.replace('CRAC_', '') for n, v in s["fan"].items() if v == 0]
        part = {n.replace('CRAC_', ''): v for n, v in s["fan"].items() if 0 < v < 1}
        print(f"{s['id']:36s} off={off} partial={part} rm={[r.replace('Rack_', '') for r in s['remove']]} P={s['row_power_kw']} supply={s['check']['supply_m3s']}")


if __name__ == "__main__":
    main()
