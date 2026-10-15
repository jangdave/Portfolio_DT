"""UE Python에서 부피 렌더링에 쓰는 클래스와 속성, 함수 이름을 조회한다. (데모 레벨을 코드로 만들기 위한 사전 조사)"""
import json
import os

import unreal

out = os.environ.get("DCT_UE_RESULT", "D:/ue_probe/discover.json")
res = {}
names = (
    "SparseVolumeTextureMaterialFactoryNew", "SparseVolumeTextureMaterialInstanceFactoryNew", "SparseVolumeTextureViewer",
    "SparseVolumeTextureViewerComponent", "AnimatedSparseVolumeTextureController", "SparseVolumeTexturePreviewAttribute",
    "SparseVolumeTextureParameterValue", "HeterogeneousVolumeComponent",
)
for cls_name in names:
    cls = getattr(unreal, cls_name, None)
    if cls is None:
        res[cls_name] = None
        continue
    try:
        cdo = unreal.get_default_object(cls)
        attrs = sorted(a for a in dir(cdo) if not a.startswith("_") and not callable(getattr(cdo, a, None)))
        funcs = sorted(a for a in dir(cdo) if not a.startswith("_") and callable(getattr(cdo, a, None)) and any(k in a for k in ("set_", "get_", "play", "stop", "create", "svt", "frame", "volume", "texture", "attribute")))
        keep = [a for a in attrs if any(k in a for k in ("volume", "texture", "frame", "attribute", "svt", "playing", "rate", "start", "end", "loop", "material", "resolution", "step", "density", "extinction", "albedo", "emissive", "scale"))]
        res[cls_name] = {"props": keep[:50], "funcs": funcs[:40]}
    except Exception as exc:  # noqa: BLE001
        res[cls_name] = f"error: {exc}"
res["svt_attrs_enum"] = [a for a in dir(unreal.SparseVolumeTexturePreviewAttribute) if not a.startswith("_")][:30] if hasattr(unreal, "SparseVolumeTexturePreviewAttribute") else None
with open(out, "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print("[ue_discover] done", flush=True)
