"""우리 솔버(hall60_sim.py)와 OpenFOAM의 랙 입구 온도(랙 60기, 정상 상태)를 비교해서 표로 출력한다. 시각화 목적의 비교다.

실행 (experiments/omniverse_probe 폴더에서, GPU가 필요한 것은 우리 솔버를 새로 돌릴 때만):
    uv run --python 3.13 python ../openfoam_baseline/compare.py                 # 저장해 둔 우리 솔버 값을 읽음(없으면 새로 계산)
    uv run --python 3.13 python ../openfoam_baseline/compare.py --rerun-ours    # 우리 솔버를 다시 돌려 저장
    uv run --python 3.13 python ../openfoam_baseline/compare.py --of-suffix _nobuoy   # OpenFOAM 변형 결과 파일 선택

우리 솔버는 hall60_sim.main()을 그대로 부르되 출력 폴더만 results/ours_<시나리오>/ 로 바꾼다
(out/hall60/은 다른 작업이 덮어쓰므로 건드리지 않는다. 프레임(.npy)은 저장하지 않는다).
 - 정상: --fail "" --duration 600     (300초 이후 변화 없음을 확인함)
 - CRAC_02+CRAC_06 정지: --fail CRAC_02,CRAC_06 --fail-time 120 --duration 900  (E0 문서 2.18장과 같은 설정)
값은 마지막 시각의 센서 temp_in(랙 앞면 5 cm 앞, 높이 1.2 m)이다. OpenFOAM 값은 같은 앵커 위치가 들어 있는 칸의 온도다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SCENARIOS = {
    "normal": {"label": "A 정상", "args": ["--fail", "", "--duration", "600"]},
    "crac02_06_off": {"label": "B CRAC_02+06 정지", "args": ["--fail", "CRAC_02,CRAC_06", "--fail-time", "120", "--duration", "900"]},
}


def read_csv(path: Path) -> dict[str, float]:
    with open(path, encoding="utf-8") as f:
        return {r["rack_id"]: float(r["temp_c"]) for r in csv.DictReader(f)}


def run_ours(name: str) -> dict[str, float]:
    """hall60_sim.main()을 우리 폴더로 출력을 돌려서 실행하고, 마지막 시각의 랙 입구 온도를 저장해 돌려준다."""
    sys.path.insert(0, str(HERE.parent / "omniverse_probe"))
    import hall60_sim as h

    out = RES / f"ours_{name}"
    out.mkdir(parents=True, exist_ok=True)
    h.OUT = out
    argv = ["hall60_sim.py", "--every", "100000"] + SCENARIOS[name]["args"]
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
    (RES / f"ours_rack_inlet_{name}.csv").write_text("rack_id,temp_c\n" + "".join(f"{k},{v:.3f}\n" for k, v in sorted(vals.items())), encoding="utf-8")
    meta = {"hall60_sim_sha1": hashlib.sha1((HERE.parent / "omniverse_probe" / "hall60_sim.py").read_bytes()).hexdigest()[:12],
            "argv": argv[1:], "result_time_s": float(last[0])}
    (RES / f"ours_rack_inlet_{name}.meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    # 큰 부산물(단면 그림 등)은 저장소에 올리지 않는다. 필요 없으면 지워도 된다.
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
    ap.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    a = ap.parse_args()
    lines = []
    for name in a.scenarios:
        ours_p = RES / f"ours_rack_inlet_{name}.csv"
        ours = run_ours(name) if (a.rerun_ours or not ours_p.exists()) else read_csv(ours_p)
        of_p = RES / f"rack_inlet_{name}{a.of_suffix}.csv"
        if not of_p.exists():
            lines.append(f"[{SCENARIOS[name]['label']}] OpenFOAM 결과 파일이 없다: {of_p.name}")
            continue
        of = read_csv(of_p)
        ids = sorted(ours)
        assert ids == sorted(of), "랙 목록이 다르다"
        o = np.array([ours[i] for i in ids]); f = np.array([of[i] for i in ids])
        so, sf = stats(o, ids), stats(f, ids)
        d = f - o
        rmse = float(np.sqrt((d ** 2).mean())); bias = float(d.mean()); mae = float(np.abs(d).mean())
        corr = float(np.corrcoef(o, f)[0, 1]) if o.std() > 1e-9 and f.std() > 1e-9 else float("nan")
        worst = np.argsort(-np.abs(d))[:3]
        lines += [
            f"### {SCENARIOS[name]['label']}  (OpenFOAM 파일: {of_p.name})",
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
    text = "\n".join(lines)
    print(text)
    (RES / f"comparison{a.of_suffix}.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
