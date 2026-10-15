"""열려 있는 .blend 파일을 USD로 내보낸다. 이후 `scripts/usd_tools/finalize_asset.py`로 마무리한다.

실행 (저장소 루트에서):
    blender -b blender/rack_blockout.blend --python blender/scripts/export_usd.py -- usd/assets/_rack_raw.usd

- 사용자 속성(assetType, metric 등)은 `dct:` 접두로 내보낸다. 타입은 string이라 마무리 단계에서 token으로 바꾼다.
"""
from __future__ import annotations

import sys

import bpy


def main() -> None:
    out = sys.argv[sys.argv.index("--") + 1]
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
    )
    print("내보냄:", out)


main()
