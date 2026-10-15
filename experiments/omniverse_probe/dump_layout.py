"""poc_hall.usda에서 랙과 CRAC의 위치와 크기(cm)를 JSON으로 저장한다. UE 데모 레벨에서 같은 위치에 상자를 놓기 위한 자료다."""
import json
from pathlib import Path

import thermal_poc as tp

OUT = Path(__file__).resolve().parent / "out"
scene = tp.read_scene(OUT / "poc_hall.usda")
layout = {
    "hall_cm": list(tp.HALL_CM),
    "racks": [{"name": r["name"], "min": list(r["min"]), "max": list(r["max"])} for r in scene["racks"]],
    "cracs": [{"name": c["name"], "min": list(c["min"]), "max": list(c["max"])} for c in scene["cracs"]],
}
(OUT / "layout.json").write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")
print("racks", len(layout["racks"]), "cracs", len(layout["cracs"]), "hall", layout["hall_cm"])
