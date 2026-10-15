"""텍스처가 이음새 없이 이어지는지 눈으로 확인하는 이미지를 만든다 (줄여서 2x2로 이어 붙인다).

실행 (저장소 루트에서):
    uv run --python 3.13 --with numpy --with pillow python blender/scripts/check_texture_tiling.py
출력: blender/previews/tex_tile_<이름>.png (1536x1536), tex_crop_<이름>.png (원본 1:1 잘라낸 1400x1400)
"""
from pathlib import Path

from PIL import Image

src = Path("blender/textures/building")
out = Path("blender/previews")
out.mkdir(parents=True, exist_ok=True)
for name in ("T_BldgPanelMetal_BaseColor", "T_BldgConcrete_BaseColor", "T_Asphalt_BaseColor", "T_BldgRoof_BaseColor",
             "T_BldgPanelMetal_Normal", "T_BldgConcrete_Normal", "T_Asphalt_Normal", "T_BldgRoof_Normal"):
    im = Image.open(src / f"{name}.png").convert("RGB")
    assert im.size == (4096, 4096), (name, im.size)
    sm = im.resize((768, 768), Image.LANCZOS)
    sheet = Image.new("RGB", (1536, 1536))
    for i in range(2):
        for j in range(2):
            sheet.paste(sm, (i * 768, j * 768))
    sheet.save(out / f"tex_tile_{name}.png")
    # 이음 부분(4096 가장자리)을 원본 크기로 보기 위해 가장자리를 가운데로 돌려서 자른다
    shifted = Image.new("RGB", (1400, 1400))
    for dx, ox in ((0, 700), (4096 - 700, 0)):
        for dy, oy in ((0, 700), (4096 - 700, 0)):
            shifted.paste(im.crop((dx, dy, dx + 700, dy + 700)), (ox, oy))
    shifted.save(out / f"tex_crop_{name}.png")
    print("확인 이미지:", name)
