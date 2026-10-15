"""CC0 텍스처(ambientCG)를 내려받아 건물 외관 텍스처 폴더에 이 프로젝트의 이름 규칙으로 놓는다.

사용 (저장소 루트에서):
    python scripts/fetch_cc0_textures.py            # blender/textures/cc0_sources.json의 자산을 모두 받는다
    python scripts/fetch_cc0_textures.py --force    # 받아 둔 압축 파일도 다시 받는다

    python scripts/fetch_cc0_textures.py --sources blender/textures/cc0_sources_hall.json --out blender/textures/hall   # 서버 홀 내부용(목록과 출력 폴더를 바꿔 받는다)
- 목록과 크기: `blender/textures/cc0_sources.json` (자산 ID, 접두 이름, 실제 크기(cm), 받을 맵)
- 받는 곳: 압축 파일은 `blender/textures/cc0_cache/`(Git 제외), 결과는 `blender/textures/building/`(Git 제외)
- 노멀은 OpenGL 규약(`NormalGL`)을 받는다. 기존 절차 텍스처와 같은 규약이라 Blender 재질과 USD 규칙은 그대로다.
- 외부 파일은 신뢰할 수 없는 데이터로 다룬다. 압축 파일에서 목록에 있는 맵 파일 이름만 꺼내 쓰고, 경로 이동(`..`)이 있는 이름은 건너뛴다.
- 목록에 `normal_strength`(1보다 작음)가 있으면 노멀 맵의 기울기를 그만큼 줄여서 저장한다. 먼 거리에서 반짝이는 노이즈를 줄이기 위한 것이다(원본 파일은 cc0_cache의 압축 파일에 그대로 있다). 이때만 numpy, pillow가 필요하다:
    uv run --python 3.13 --with numpy --with pillow python scripts/fetch_cc0_textures.py
- 결과로 파일 크기, 해상도, SHA-256을 출력한다(출처 기록용).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "blender" / "textures" / "cc0_sources.json"
UA = {"User-Agent": "Mozilla/5.0 (DC-Twin texture fetch)"}


def api_download_link(asset_id: str, attribute: str) -> tuple[str, int]:
    """ambientCG API에서 (다운로드 주소, 크기)를 찾는다."""
    url = "https://ambientcg.com/api/v2/full_json?" + urllib.parse.urlencode({"id": asset_id, "include": "downloadData"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = json.load(r)
    assets = data.get("foundAssets") or []
    if not assets:
        raise SystemExit(f"자산을 찾지 못했다: {asset_id}")
    for d in assets[0]["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]:
        if d["attribute"] == attribute:
            return d["downloadLink"], int(d["size"])
    raise SystemExit(f"{asset_id}에 {attribute} 압축 파일이 없다")


def download(url: str, dst: Path, size: int) -> None:
    tmp = dst.with_suffix(".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
        got = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            got += len(chunk)
    if size and got != size:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"받은 크기가 다르다: {got} / {size} ({url})")
    tmp.replace(dst)


def image_size(path: Path) -> tuple[int, int] | None:
    """PNG, JPEG 해상도를 읽는다(표준 라이브러리만 사용)."""
    b = path.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def weaken_normal(path: Path, strength: float) -> None:
    """노멀 맵(OpenGL 규약)의 기울기(x, y)를 strength배로 줄이고 z를 다시 맞춘다."""
    import numpy as np
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0 * 2.0 - 1.0
    a[..., 0] *= strength
    a[..., 1] *= strength
    xy2 = np.clip(a[..., 0] ** 2 + a[..., 1] ** 2, 0.0, 0.999)
    a[..., 2] = np.sqrt(1.0 - xy2)
    out = ((a * 0.5 + 0.5).clip(0, 1) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(out).save(path, quality=95, subsampling=0) if path.suffix.lower() in (".jpg", ".jpeg") else Image.fromarray(out).save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CC0 텍스처 내려받기")
    ap.add_argument("--sources", type=Path, default=SOURCES)
    ap.add_argument("--cache", type=Path, default=ROOT / "blender" / "textures" / "cc0_cache")
    ap.add_argument("--out", type=Path, default=ROOT / "blender" / "textures" / "building")
    ap.add_argument("--force", action="store_true", help="받아 둔 압축 파일도 다시 받는다")
    args = ap.parse_args(argv)
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cfg = json.loads(args.sources.read_text(encoding="utf-8"))
    attribute = cfg["attribute"]
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"출처 {cfg['provider']} | 라이선스 {cfg['license']} ({cfg['license_url']}) | 해상도 {attribute}")
    for a in cfg["assets"]:
        zip_path = args.cache / f"{a['id']}_{attribute}.zip"
        if args.force or not zip_path.exists():
            url, size = api_download_link(a["id"], attribute)
            print(f"받는 중 {a['id']} ({size / 1048576:.0f} MB) {url}")
            download(url, zip_path, size)
        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        with zipfile.ZipFile(zip_path) as z:
            names = {n.rsplit("/", 1)[-1]: n for n in z.namelist() if ".." not in n and not n.startswith("/")}
            for src_map, dst_map in a["maps"].items():
                want = next((n for base, n in names.items() if base.endswith(f"_{src_map}.jpg") or base.endswith(f"_{src_map}.png")), None)
                if want is None:
                    raise SystemExit(f"{a['id']} 압축 파일에 {src_map} 맵이 없다 (있는 파일: {sorted(names)[:8]})")
                ext = Path(want).suffix
                out = args.out / f"{a['prefix']}_{dst_map}{ext}"
                out.write_bytes(z.read(want))
                if dst_map == "Normal" and a.get("normal_strength", 1.0) < 1.0:
                    weaken_normal(out, float(a["normal_strength"]))
                wh = image_size(out)
                print(f"  {out.name}: {out.stat().st_size / 1048576:.1f} MB, {wh[0]}x{wh[1]}" if wh else f"  {out.name}: {out.stat().st_size / 1048576:.1f} MB")
        extra = f" | 노멀 세기 {a['normal_strength']}배" if a.get("normal_strength", 1.0) < 1.0 else ""
        print(f"  zip SHA-256 {sha}  | 실제 크기 {a['tile_cm']} cm{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
