"""Blender가 내보낸 USD를 이 프로젝트의 에셋 규칙에 맞게 마무리한다.

하는 일:
1. `/root` 아래에 있는 가장 바깥 오브젝트를 최상위로 올리고 `/root`를 없앤다.
2. 기본 prim(defaultPrim) 지정, 단위 cm(0.01), 위쪽 축 Z 지정
3. `dct:assetType`, `dct:zone`, `dct:metric`을 string에서 token으로 바꾼다.

사용 (scripts/usd_tools 폴더에서):
    uv run --python 3.13 python finalize_asset.py <입력.usd> <출력.usda>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom

TOKEN_ATTRS = ("dct:assetType", "dct:zone", "dct:metric")


def flatten_root(stage: Usd.Stage, root_path: str = "/root") -> str:
    """`/root` 아래 최상위 prim 하나를 stage의 최상위로 올린다. 올라온 prim 경로를 돌려준다."""
    root = stage.GetPrimAtPath(root_path)
    if not root:
        tops = [p for p in stage.GetPseudoRoot().GetChildren() if p.GetName() not in ("_materials",)]
        if len(tops) != 1:
            raise ValueError(f"최상위 prim이 하나가 아니다: {[str(p.GetPath()) for p in tops]}")
        return str(tops[0].GetPath())

    children = [c for c in root.GetChildren() if c.GetName() != "_materials"]
    if len(children) != 1:
        raise ValueError(f"{root_path} 아래 오브젝트가 하나가 아니다: {[c.GetName() for c in children]}")
    child = children[0]

    layer = stage.GetRootLayer()
    new_path = Sdf.Path("/" + child.GetName())
    edit = Sdf.BatchNamespaceEdit()
    edit.Add(child.GetPath(), new_path)
    # 재료(_materials)도 /root 밖으로 옮겨 /root를 지운다
    mats = stage.GetPrimAtPath(f"{root_path}/_materials")
    if mats:
        edit.Add(mats.GetPath(), Sdf.Path(f"/{child.GetName()}/_materials"))
    if not layer.Apply(edit):
        raise RuntimeError("prim 이동에 실패했다")
    stage.RemovePrim(root_path)
    return str(new_path)


def to_token(stage: Usd.Stage) -> int:
    """string 속성을 token으로 바꾸고 바뀐 개수를 돌려준다."""
    changed = 0
    for prim in stage.Traverse():
        for name in TOKEN_ATTRS:
            attr = prim.GetAttribute(name)
            if not attr or attr.GetTypeName() == Sdf.ValueTypeNames.Token:
                continue
            value = attr.Get()
            prim.RemoveProperty(name)
            new_attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Token, custom=True)
            new_attr.Set(str(value))
            changed += 1
    return changed


def finalize(src: Path, dst: Path) -> dict:
    stage = Usd.Stage.Open(str(src))
    if stage is None:
        raise RuntimeError(f"파일을 열 수 없다: {src}")
    top = flatten_root(stage)
    stage.SetDefaultPrim(stage.GetPrimAtPath(top))
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    n = to_token(stage)
    stage.GetRootLayer().Export(str(dst))
    return {"default_prim": top, "token_attrs_changed": n, "output": str(dst)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Blender USD를 에셋 규칙에 맞게 마무리")
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    args = ap.parse_args(argv)
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    info = finalize(args.src, args.dst)
    print(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
