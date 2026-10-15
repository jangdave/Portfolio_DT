"""ovrtx가 우리 데이터센터 장면에서 어떤 데이터를 내주는지 실제로 받아 확인한다.

받아 보는 것: 색상(LdrColor, HdrColor), 법선(NormalSD), 깊이(DepthSD, DistanceToCameraSD, DistanceToImagePlaneSD),
알베도(DiffuseAlbedoSD), 카메라 기준 3D 위치(Camera3dPositionSD), 시멘틱 세그멘테이션(랙/CRAC 라벨).

사용 (이 폴더에서): uv run --python 3.13 python probe_ovrtx_outputs.py
(thermal_poc.py를 먼저 실행해서 out/poc_hall.usda가 있어야 한다.)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import ovrtx
from PIL import Image
from pxr import Gf

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
HALL = (OUT / "poc_hall.usda").resolve()
RES = (1280, 720)
AOVS = [
    "LdrColor", "HdrColor", "NormalSD", "DepthSD", "DistanceToCameraSD",
    "DistanceToImagePlaneSD", "DiffuseAlbedoSD", "Camera3dPositionSD", "SemanticSegmentation", "SemanticIdMap",
]


def look_at_matrix(eye, target, up=(0, 0, 1)) -> str:
    m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(*up)).GetInverse()
    rows = ", ".join("(" + ", ".join(f"{m[r][c]:.6f}" for c in range(4)) + ")" for r in range(4))
    return f"( {rows} )"


def build_usda() -> str:
    """poc_hall.usda 위에 바닥, 조명, 카메라, 의미 라벨, 렌더 출력을 덧씌운다."""
    sem = lambda label: (
        '(\n            prepend apiSchemas = ["SemanticsAPI:class"]\n        )\n        {\n'
        f'            string semantic:class:params:semanticData = "{label}"\n'
        '            string semantic:class:params:semanticType = "class"\n        }\n'
    )
    # 같은 이름의 over를 중복해서 쓰면 USD가 오류를 내므로, 줄(Row)마다 한 번만 열고 안에 랙을 모은다.
    nl = "\n"
    rows = []
    n = 1
    for row in ("Row01", "Row02"):
        racks = ""
        for _ in range(5):
            racks += f'            over "Rack_{n:02d}" {sem("rack")}{nl}'
            n += 1
        rows.append(f'        over "{row}" {{{nl}{racks}        }}{nl}')
    cracs = "".join(f'            over "CRAC_{i:02d}" {sem("crac")}{nl}' for i in (1, 2))
    overs = rows + [f'        over "Cooling" {{{nl}{cracs}        }}{nl}']
    ordered = ", ".join(f"<{a}>" for a in AOVS)
    var_defs = "\n".join(f'        def RenderVar "{a}"\n        {{\n            string sourceName = "{a}"\n        }}' for a in AOVS)
    matrix = look_at_matrix(eye=(400.0, 20.0, 330.0), target=(400.0, 300.0, 90.0))
    return f"""#usda 1.0
(
    subLayers = [ @{HALL.as_posix()}@ ]
    metersPerUnit = 0.01
    upAxis = "Z"
)

over "DC" {{
    over "Hall01" {{
{''.join(overs)}    }}

    def Cube "Floor" {{
        double size = 1
        double3 xformOp:translate = (400, 300, -1)
        double3 xformOp:scale = (800, 600, 2)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }}
    def DomeLight "Dome" {{
        float inputs:intensity = 700
    }}
    def DistantLight "Sun" {{
        float inputs:intensity = 2500
        double3 xformOp:rotateXYZ = (-55, 15, 0)
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }}
    def Camera "Cam" {{
        float focalLength = 16
        float horizontalAperture = 36
        matrix4d xformOp:transform = {matrix}
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
}}

def "Render" {{
    def RenderProduct "Camera" {{
        int2 resolution = {RES}
        rel camera = </DC/Cam>
        rel orderedVars = [{ordered}]
{var_defs}
    }}
}}
"""


def decode_id_map(tensor: np.ndarray) -> dict[int, str]:
    """SemanticIdMap(바이트 묶음)을 {id: 라벨}로 풀어 준다. (ovrtx 문서 예제의 방식)"""
    data = np.ascontiguousarray(tensor).view(np.uint8).reshape(-1)
    entry = np.dtype([("id", "<u4", (4)), ("label_length", "<u4"), ("label_offset", "<u4")])
    n = int.from_bytes(data[-4:].tobytes(), "little")
    entries = data[: n * entry.itemsize].view(entry).reshape(n)
    out = {}
    for e in entries:
        s, ln = int(e["label_offset"]), int(e["label_length"])
        out[int(e["id"][0])] = data[s : s + ln].tobytes().decode("utf-8").rstrip("\x00").rstrip()
    return out


def stats(a: np.ndarray) -> dict:
    f = a.astype(np.float64)
    finite = np.isfinite(f)
    return {
        "shape": list(a.shape), "dtype": str(a.dtype),
        "min": float(f[finite].min()) if finite.any() else None,
        "max": float(f[finite].max()) if finite.any() else None,
        "nonzero_fraction": round(float((a != 0).mean()), 4),
    }


def main() -> None:
    result: dict = {"resolution": list(RES), "aovs": {}}
    t0 = time.perf_counter()
    renderer = ovrtx.Renderer()
    result["renderer_create_s"] = round(time.perf_counter() - t0, 2)
    renderer.open_usd_from_string(build_usda())
    for _ in range(8):  # 장면이 안정되도록 몇 번 돌린다
        renderer.step(render_products={"/Render/Camera"}, delta_time=1.0 / 60.0)
    t0 = time.perf_counter()
    products = renderer.step(render_products={"/Render/Camera"}, delta_time=1.0 / 60.0)
    result["one_frame_s"] = round(time.perf_counter() - t0, 4)

    frame = products["/Render/Camera"].frames[0]
    result["returned_render_vars"] = sorted(frame.render_vars.keys())
    arrays = {}
    for name in AOVS:
        if name not in frame.render_vars:
            result["aovs"][name] = {"returned": False}
            continue
        mapped = frame.render_vars[name].map(device=ovrtx.Device.CPU)
        a = np.from_dlpack(mapped).copy()
        del mapped
        arrays[name] = a
        result["aovs"][name] = {"returned": True, **stats(a)}

    # 시각화 저장
    if "LdrColor" in arrays:
        Image.fromarray(arrays["LdrColor"]).save(OUT / "ovrtx_ldr.png")
    if "DistanceToImagePlaneSD" in arrays:
        d = np.squeeze(arrays["DistanceToImagePlaneSD"]).astype(np.float32)
        valid = np.isfinite(d) & (d > 0) & (d < 1e6)
        if valid.any():
            lo, hi = np.percentile(d[valid], [2, 98])
            g = np.where(valid, np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1), 1.0)
            Image.fromarray((255 * (1 - g)).astype(np.uint8)).save(OUT / "ovrtx_depth.png")
            result["depth_range_m_p2_p98"] = [round(float(lo), 1), round(float(hi), 1)]
    if "NormalSD" in arrays:
        n = arrays["NormalSD"][..., :3].astype(np.float32)
        Image.fromarray(((n * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)).save(OUT / "ovrtx_normals.png")
    if "SemanticSegmentation" in arrays and "SemanticIdMap" in arrays:
        seg = np.squeeze(arrays["SemanticSegmentation"])
        id_map = decode_id_map(arrays["SemanticIdMap"])
        result["semantic_id_map"] = {str(k): v for k, v in id_map.items()}
        counts = {id_map.get(int(i), f"id{int(i)}"): int((seg == i).sum()) for i in np.unique(seg)}
        result["semantic_pixel_counts"] = counts
        palette = {}
        img = np.zeros(seg.shape + (3,), np.uint8)
        rng = np.random.default_rng(3)
        for i in np.unique(seg):
            palette[int(i)] = rng.integers(60, 255, 3)
            img[seg == i] = palette[int(i)]
        Image.fromarray(img).save(OUT / "ovrtx_semantic.png")
    if "Camera3dPositionSD" in arrays:
        p = arrays["Camera3dPositionSD"][..., :3].astype(np.float32)
        result["camera3d_position_sample_center_px_m"] = [round(float(x), 1) for x in p[RES[1] // 2, RES[0] // 2]]

    (OUT / "ovrtx_outputs.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in result if k != "aovs"}, indent=2, ensure_ascii=False))
    for k, v in result["aovs"].items():
        print(k, v)
    # 종료 시 프로세스가 멈추는 현상이 한 번 있었다(원인 미확인). 결과를 저장한 뒤 바로 끝낸다.
    os._exit(0)


if __name__ == "__main__":
    main()
