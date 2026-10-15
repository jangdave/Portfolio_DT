"""열려 있는 .blend 파일을 USD로 내보낸다. 이후 `scripts/usd_tools/finalize_asset.py`로 마무리한다.

실행 (저장소 루트에서):
    blender -b blender/rack_blockout.blend --python blender/scripts/export_usd.py -- usd/assets/_rack_raw.usd

- 사용자 속성(assetType, metric 등)은 `dct:` 접두로 내보낸다. 타입은 string이라 마무리 단계에서 token으로 바꾼다.
- 텍스처가 있는 에셋(건물 외관 등)은 `--textures NEW`를 끝에 붙인다. 출력 USD 옆의 `textures/` 폴더에 이미지를 복사한다.
    blender -b blender/building_exterior.blend --python blender/scripts/export_usd.py -- <스크래치>/building_raw.usd --textures NEW
  (붙이지 않으면 기존 동작 그대로이며 이미지를 복사하지 않는다. 랙, CRAC 내보내기에는 영향이 없다.)
"""
from __future__ import annotations

import sys

import bpy


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    out = args[0]
    extra = {}
    if "--textures" in args:
        extra["export_textures_mode"] = args[args.index("--textures") + 1]  # KEEP / PRESERVE / NEW
        extra["overwrite_textures"] = True
        extra["relative_paths"] = True
    bpy.ops.wm.usd_export(
        filepath=out,
        check_existing=False,
        selected_objects_only=False,
        export_animation=False,
        export_materials=True,
        generate_preview_surface=True,
        export_uvmaps=True,
        export_normals=True,
        use_instancing=False,
        evaluation_mode="RENDER",
        convert_scene_units="CENTIMETERS",
        root_prim_path="/root",
        export_custom_properties=True,
        custom_properties_namespace="dct",
        author_blender_name=False,
        export_lights=False,
        export_cameras=False,
        triangulate_meshes=False,
        **extra,
    )
    print("내보냄:", out)


main()
