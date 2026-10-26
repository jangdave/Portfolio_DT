"""AI 대리 모델 1단계용 샘플 40개를 설계해서 samples.json으로 저장한다(시드 고정, 같은 시드면 항상 같은 결과).

실행 (experiments/omniverse_probe 폴더에서):
    uv run --python 3.13 python ../openfoam_baseline/surrogate/design_samples.py

샘플 명세: {id, group, fan:{CRAC_01..08: 0~1}, row_power_kw:[6개], remove:[랙 이름], holdout:false}
- 구성: 정상(전력만 변화) 4, CRAC 1대 고장 10, 같은 통로 2대 고장 8, 서로 다른 통로 2대 고장 6, 팬 부분 저하 6, 랙 제거 + 고장 6.
- 줄별 전력은 6~14 kW(줄마다 다르게). 랙 이름 번호로 줄을 정한다(Rack_01~10 = 1번 줄).
- 통로: CRAC_01~04 = 통로 0~3(y 위치 순서), CRAC_05~08도 같은 통로 0~3(반대쪽 벽).
- 보류(hold-out) 평가용: 이미 계산한 A(정상), B(CRAC_02+06), D(CRAC_02), E(랙 5, 6 제거 + CRAC_02+06)를 holdout:true로 표시한다(전력 10 kW 균일).
  OpenFOAM 값은 results/ 에 이미 있고(existing_of), 우리 솔버 값만 새로 계산한다.
- 점검: 장면에서 hall60_sim.crac_returns로 유량을 계산해 (1) 켜진 CRAC가 하나 이상 (2) 통로 배기 = CRAC 회수 + 새는 양 (3) 급기 합 > 0 을 확인하고,
  샘플마다 supply, leak를 기록한다. 같은 이름 규칙은 hall60_sim.py의 것을 읽기만 한다.
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

SEED = 20261021
CRACS = [f"CRAC_{i:02d}" for i in range(1, 9)]
AISLE = {n: (int(n.split("_")[1]) - 1) % 4 for n in CRACS}
RACKS = [f"Rack_{i:02d}" for i in range(1, 61)]


def main() -> None:
    rs = np.random.RandomState(SEED)

    def powers() -> list[float]:
        return [round(float(x), 1) for x in rs.uniform(6.0, 14.0, 6)]

    def fan_of(off=(), partial=None) -> dict:
        f = {n: 1.0 for n in CRACS}
        for n in off:
            f[n] = 0.0
        for n, v in (partial or {}).items():
            f[n] = round(float(v), 2)
        return f

    S = []

    def add(group, fan, remove=()):
        S.append({"id": f"s{len(S)+1:02d}_{group}", "group": group, "fan": fan, "row_power_kw": powers(), "remove": list(remove), "holdout": False})

    for _ in range(4):
        add("normal", fan_of())
    singles = [CRACS[i % 8] for i in range(8)] + [CRACS[i] for i in rs.choice(8, 2, replace=False)]
    for n in singles:
        add("one_crac_off", fan_of([n]))
    same = [(f"CRAC_{a+1:02d}", f"CRAC_{a+5:02d}") for a in range(4)] * 2
    for pair in same:
        add("same_aisle_two_off", fan_of(pair))
    for _ in range(6):
        while True:
            a, b = rs.choice(8, 2, replace=False)
            if AISLE[CRACS[a]] != AISLE[CRACS[b]]:
                break
        add("diff_aisle_two_off", fan_of([CRACS[a], CRACS[b]]))
    for _ in range(6):
        k = int(rs.randint(2, 5))
        idx = rs.choice(8, k, replace=False)
        add("fan_derated", fan_of(partial={CRACS[i]: rs.uniform(0.3, 0.8) for i in idx}))
    for _ in range(6):
        nrm = int(rs.randint(1, 4))
        rem = sorted(RACKS[i] for i in rs.choice(60, nrm, replace=False))
        off = [CRACS[i] for i in rs.choice(8, int(rs.randint(1, 3)), replace=False)]
        add("remove_and_fail", fan_of(off), rem)
    assert len(S) == 40, len(S)

    held = [
        {"id": "holdout_A_normal", "group": "holdout", "fan": fan_of(), "row_power_kw": [10.0] * 6, "remove": [], "holdout": True, "existing_of": "rack_inlet_normal.csv"},
        {"id": "holdout_B_crac02_06_off", "group": "holdout", "fan": fan_of(["CRAC_02", "CRAC_06"]), "row_power_kw": [10.0] * 6, "remove": [], "holdout": True, "existing_of": "rack_inlet_crac02_06_off.csv"},
        {"id": "holdout_D_crac02_off", "group": "holdout", "fan": fan_of(["CRAC_02"]), "row_power_kw": [10.0] * 6, "remove": [], "holdout": True, "existing_of": "rack_inlet_crac02_off.csv"},
        {"id": "holdout_E_rm05_06_crac02_06_off", "group": "holdout", "fan": fan_of(["CRAC_02", "CRAC_06"]), "row_power_kw": [10.0] * 6, "remove": ["Rack_05", "Rack_06"], "holdout": True, "existing_of": "rack_inlet_rm05_06_crac02_06_off.csv"},
    ]

    # 물리 점검
    base = h.ROOT / "usd" / "scenes" / "hall01.usda"
    tmp = Path(tempfile.gettempdir()) / "dct_design_check.usda"
    problems = []
    for smp in S + held:
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
                        "aisle_exhaust_m3s": [round(float(x), 2) for x in exhaust], "total_power_kw": round(float(sum(
                            smp["row_power_kw"][(int(r["name"].split("_")[1]) - 1) // 10] for r in hall["racks"])), 1), "ok": bool(ok)}
        if not ok:
            problems.append(smp["id"])
    tmp.unlink(missing_ok=True)
    out = {"seed": SEED, "note": "holdout:true 는 기존 A, B, D, E(OpenFOAM 값은 results/에 있음). 학습에 쓰지 말고 평가용으로만 쓴다.", "samples": S + held}
    (HERE / "samples.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"샘플 {len(S)}개 + 보류 {len(held)}개 저장. 점검 실패: {problems or '없음'}")
    for s in S + held:
        off = [n.replace('CRAC_', '') for n, v in s["fan"].items() if v == 0]
        part = {n.replace('CRAC_', ''): v for n, v in s["fan"].items() if 0 < v < 1}
        print(f"{s['id']:34s} off={off} partial={part} rm={[r.replace('Rack_','') for r in s['remove']]} P={s['row_power_kw']} supply={s['check']['supply_m3s']} leak={s['check']['leak_m3s']}")


if __name__ == "__main__":
    main()
