"""우리 솔버(hall60_sim.py)와 OpenFOAM의 랙 입구 온도(정상 상태)를 비교해서 표로 출력한다. 시각화 목적의 비교다.

실행 (experiments/omniverse_probe 폴더에서, GPU가 필요한 것은 우리 솔버를 새로 돌릴 때만):
    uv run --python 3.13 python ../openfoam_baseline/compare.py                       # 모든 사례, 저장해 둔 우리 솔버 값을 읽음(없으면 새로 계산)
    uv run --python 3.13 python ../openfoam_baseline/compare.py --rerun-ours          # 우리 솔버를 현재 코드로 다시 돌려 저장
    uv run --python 3.13 python ../openfoam_baseline/compare.py --scenarios crac03_07_off crac02_off
    uv run --python 3.13 python ../openfoam_baseline/compare.py --of-suffix _nobuoy   # OpenFOAM 변형 결과 파일 선택
    uv run --python 3.13 python ../openfoam_baseline/compare.py --ours-tag ""         # PR #55 이전 방식으로 저장한 옛 우리 값(_pr55 없는 파일)

우리 솔버는 hall60_sim.main()을 그대로 부르되 출력 폴더만 results/ours_<사례>/ 로 바꾼다
(out/hall60/은 다른 작업이 덮어쓰므로 건드리지 않는다). 우리 값 파일 이름은 ours_rack_inlet_<사례><ours-tag>.csv 이고
기본 태그는 `_pr55`(PR #55 이후의 hall60_sim.py: 지붕 틈 열 보존, MacCormack 이류)다. 옛 태그 없는 파일은 지우지 않는다.
사례(SCENARIOS): 정지 목록 --fail, 지속 시간은 정상 600초, 고장 사례 900초(120초에 정지, E0 문서 2.18장과 같은 설정).
값은 마지막 시각의 센서 temp_in(랙 앞면 5 cm 앞, 높이 1.2 m)이다. OpenFOAM 값은 같은 앵커 위치가 들어 있는 칸의 온도다.
랙 배치 변경 사례(whatif_*)는 layout_whatif.apply_edits로 만든 편집 장면(임시 폴더)을 같은 방식으로 돌린다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
FAIL_ARGS = lambda f: ["--fail", f, "--fail-time", "120", "--duration", "900"]
SCENARIOS = {
    "normal": {"label": "A 정상", "args": ["--fail", "", "--duration", "600"]},
    "crac02_06_off": {"label": "B CRAC_02+06 정지", "args": FAIL_ARGS("CRAC_02,CRAC_06")},
    "crac03_07_off": {"label": "C CRAC_03+07 정지", "args": FAIL_ARGS("CRAC_03,CRAC_07")},
    "crac02_off": {"label": "D CRAC_02 한 대 정지", "args": FAIL_ARGS("CRAC_02")},
    "rm05_06_crac02_06_off": {"label": "E 랙 5, 6번 제거 + CRAC_02+06 정지", "args": FAIL_ARGS("CRAC_02,CRAC_06"),
                              "edit": {"remove": ["Rack_05", "Rack_06"]}},
}


def read_csv(path: Path) -> dict[str, float]:
    with open(path, encoding="utf-8") as f:
        return {r["rack_id"]: float(r["temp_c"]) for r in csv.DictReader(f)}


def run_ours(name: str, tag: str) -> dict[str, float]:
    """현재 hall60_sim.py로 이 사례를 돌리고, 마지막 시각의 랙 입구 온도를 저장해 돌려준다."""
    sys.path.insert(0, str(HERE.parent / "omniverse_probe"))
    import hall60_sim as h

    spec = SCENARIOS[name]
    out = RES / f"ours_{name}"
    out.mkdir(parents=True, exist_ok=True)
    argv = ["hall60_sim.py", "--every", "100000"] + spec["args"]
    if "edit" in spec:
        import layout_whatif as lw
        scene = Path(tempfile.gettempdir()) / f"dct_scene_{name}.usda"  # 저장소 밖 임시 위치
        lw.apply_edits(h.ROOT / "usd" / "scenes" / "hall01.usda", scene, spec["edit"])
        argv += ["--scene", str(scene)]
    h.OUT = out
    old = sys.argv
    sys.argv = argv
    try:
        h.main()
    finally:
        sys.argv = old
    with open(out / "sensors.csv", encoding="utf-8") as f:
        r = list(csv.reader(f))
    hdr, last = r[0], r[-1]
    vals = {c.split(".")[0]: float(last[i]) for i, c in enumerate(hdr) if c.endswith(".temp_in")}
    (RES / f"ours_rack_inlet_{name}{tag}.csv").write_text("rack_id,temp_c\n" + "".join(f"{k},{v:.3f}\n" for k, v in sorted(vals.items())), encoding="utf-8")
    meta = {"hall60_sim_sha1": hashlib.sha1((HERE.parent / "omniverse_probe" / "hall60_sim.py").read_bytes()).hexdigest()[:12],
            "argv": argv[1:], "result_time_s": float(last[0]), "edit": spec.get("edit")}
    (RES / f"ours_rack_inlet_{name}{tag}.meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    for f in list((out / "frames").glob("*.npy")) if (out / "frames").exists() else []:
        f.unlink()  # 큰 프레임은 남기지 않는다
    return vals


def stats(v: np.ndarray, ids: list[str]) -> dict:
    pos = np.array([(int(i.split("_")[1]) - 1) % 10 for i in ids])
    end = (pos == 0) | (pos == 9)
    return {"mean": v.mean(), "max": v.max(), "min": v.min(), "end": v[end].mean(), "mid": v[~end].mean(),
            "top5": [ids[i].replace("Rack_", "") for i in np.argsort(-v)[:5]]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun-ours", action="store_true")
    ap.add_argument("--of-suffix", default="", help="OpenFOAM 결과 파일 접미(예: _front_mean, _nobuoy)")
    ap.add_argument("--ours-tag", default="_pr55", help="우리 값 파일 이름 접미(기본 _pr55 = PR #55 이후 코드)")
    ap.add_argument("--scenarios", nargs="*", default=["normal", "crac02_06_off"], choices=list(SCENARIOS))
    a = ap.parse_args()
    lines, rows = [], []
    for name in a.scenarios:
        ours_p = RES / f"ours_rack_inlet_{name}{a.ours_tag}.csv"
        ours = run_ours(name, a.ours_tag) if (a.rerun_ours or not ours_p.exists()) else read_csv(ours_p)
        of_p = RES / f"rack_inlet_{name}{a.of_suffix}.csv"
        if not of_p.exists():
            lines.append(f"[{SCENARIOS[name]['label']}] OpenFOAM 결과 파일이 없다: {of_p.name}")
            continue
        of = read_csv(of_p)
        ids = sorted(ours)
        assert ids == sorted(of), f"랙 목록이 다르다: {sorted(set(ids) ^ set(of))}"
        o = np.array([ours[i] for i in ids]); f = np.array([of[i] for i in ids])
        so, sf = stats(o, ids), stats(f, ids)
        d = f - o
        rmse = float(np.sqrt((d ** 2).mean())); bias = float(d.mean()); mae = float(np.abs(d).mean())
        corr = float(np.corrcoef(o, f)[0, 1]) if o.std() > 1e-9 and f.std() > 1e-9 else float("nan")
        worst = np.argsort(-np.abs(d))[:3]
        block = [
            f"### {SCENARIOS[name]['label']}  (랙 {len(ids)}기, OpenFOAM 파일: {of_p.name}, 우리 값 태그: '{a.ours_tag}')",
            "",
            "| 항목 | 우리 솔버 | OpenFOAM | 차이(OF-우리) |",
            "|---|---|---|---|",
            f"| 랙 입구 평균 (도) | {so['mean']:.2f} | {sf['mean']:.2f} | {sf['mean']-so['mean']:+.2f} |",
            f"| 랙 입구 최대 (도) | {so['max']:.2f} | {sf['max']:.2f} | {sf['max']-so['max']:+.2f} |",
            f"| 랙 입구 최소 (도) | {so['min']:.2f} | {sf['min']:.2f} | {sf['min']-so['min']:+.2f} |",
            f"| 줄 끝 랙 평균 (도) | {so['end']:.2f} | {sf['end']:.2f} | {sf['end']-so['end']:+.2f} |",
            f"| 줄 가운데 랙 평균 (도) | {so['mid']:.2f} | {sf['mid']:.2f} | {sf['mid']-so['mid']:+.2f} |",
            f"| 줄 끝 - 가운데 (도) | {so['end']-so['mid']:+.2f} | {sf['end']-sf['mid']:+.2f} | {(sf['end']-sf['mid'])-(so['end']-so['mid']):+.2f} |",
            f"| 가장 뜨거운 랙 5기 | {', '.join(so['top5'])} | {', '.join(sf['top5'])} | |",
            "",
            f"랙별 오차(OF-우리): RMSE {rmse:.2f} 도, 평균 오차(편향) {bias:+.2f} 도, 평균 절대 오차 {mae:.2f} 도, 상관계수 {corr:.2f}. "
            f"차이가 가장 큰 랙: " + ", ".join(f"{ids[i]}({d[i]:+.1f})" for i in worst),
            "",
        ]
        lines += block
        (RES / f"comparison_{name}{a.of_suffix}.md").write_text("\n".join(block), encoding="utf-8")
        rows.append((SCENARIOS[name]["label"], so, sf, rmse, bias, corr))
    if len(rows) > 1:
        t = ["### 요약 (우리 솔버 / OpenFOAM)", "",
             "| 사례 | 평균 | 최대 | 줄 끝 평균 | 가운데 평균 | 끝-가운데 | RMSE | 편향 | 상관 |", "|---|---|---|---|---|---|---|---|---|"]
        for lab, so, sf, rmse, bias, corr in rows:
            t.append(f"| {lab} | {so['mean']:.2f} / {sf['mean']:.2f} | {so['max']:.2f} / {sf['max']:.2f} | {so['end']:.2f} / {sf['end']:.2f} | "
                     f"{so['mid']:.2f} / {sf['mid']:.2f} | {so['end']-so['mid']:+.2f} / {sf['end']-sf['mid']:+.2f} | {rmse:.2f} | {bias:+.2f} | {corr:.2f} |")
        t.append("")
        lines += t
        (RES / f"comparison_summary{a.ours_tag}{a.of_suffix}.md").write_text("\n".join(t), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
