"""학습 샘플 전체로 예측기를 학습해 model.pkl로 저장한다(저장소에는 올리지 않는다, 몇 초 걸린다).

사용 (이 폴더에서):
    uv run --python 3.13 python train_predictor.py [--only-converged] [--out model.pkl]
센서 생성기(L2)가 `ResidualPredictor.load("model.pkl")`로 읽어서 `predict(...)`를 부른다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import predictor as pr
import residual_model as rm

ap = argparse.ArgumentParser()
ap.add_argument("--only-converged", action="store_true", help="수렴한 샘플만 학습에 쓴다(기본은 미수렴 9개 포함)")
ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "model.pkl")
a = ap.parse_args()
samples_json = rm.BASE / "surrogate" / "samples.json"
specs = {s["id"]: s for s in json.loads(samples_json.read_text(encoding="utf-8"))["samples"]}
data = [d for d in rm.load_dataset(rm.RES / "surrogate", samples_json, a.only_converged) if not d["holdout"]]
p = pr.ResidualPredictor().fit(data, specs)
p.save(a.out)
print(f"학습 샘플 {len(data)}개로 학습, 저장: {a.out} ({a.out.stat().st_size / 1e6:.1f} MB)")
print(f"학습 범위: 줄 전력 {p.power_range[0]:g}~{p.power_range[1]:g} kW, 제거한 랙 최대 {p.max_removed}기")
