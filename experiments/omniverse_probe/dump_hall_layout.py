"""홀 장면(USD)에서 홀 크기와 장비 위치(cm)를 JSON으로 저장한다. UE 데모 레벨이 같은 위치에 상자를 놓기 위한 자료다.

사용 (이 폴더에서): uv run --python 3.13 python dump_hall_layout.py [장면.usda] [출력.json]
"""
import json
import sys
from pathlib import Path

import hall60_sim as hs

scene = Path(sys.argv[1]) if len(sys.argv) > 1 else hs.ROOT / "usd" / "scenes" / "hall01.usda"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else hs.OUT / "layout.json"
hall = hs.read_hall(scene)
box = lambda d: {"name": d["name"], "min": list(d["min"]), "max": list(d["max"])}
layout = {
    "hall_cm": list(hall["size_cm"]),
    "racks": [box(d) for d in hall["racks"]],
    "cracs": [box(d) for d in hall["cracs"]],
    "vents": [box(d) for d in hall["vents"]],
    "panels": [box(d) for d in hall["panels"]],
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")
print("racks", len(layout["racks"]), "cracs", len(layout["cracs"]), "vents", len(layout["vents"]), "hall", layout["hall_cm"], "->", out)
