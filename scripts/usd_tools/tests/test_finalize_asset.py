"""finalize_asset.py 테스트: /root를 없앤 뒤에도 재질 바인딩이 새 경로를 가리키는지 확인한다."""
from __future__ import annotations

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdShade

from finalize_asset import finalize

RAW = """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
)
def Xform "root"
{
    def Xform "Rack"
    {
        string dct:assetType = "rack"
        def Mesh "Body"
        {
            rel material:binding = </root/_materials/M_Body>
        }
    }
    def Scope "_materials"
    {
        def Material "M_Body"
        {
            token outputs:surface.connect = </root/_materials/M_Body/Shader.outputs:surface>
            def Shader "Shader"
            {
                token outputs:surface
            }
        }
    }
}
"""


def test_material_binding_follows_moved_materials(tmp_path: Path):
    src = tmp_path / "raw.usda"
    src.write_text(RAW, encoding="utf-8")
    dst = tmp_path / "out.usda"
    info = finalize(src, dst)
    assert info["relationships_retargeted"] == 2  # 재질 바인딩 1 + 셰이더 연결 1
    stage = Usd.Stage.Open(str(dst))
    mesh = stage.GetPrimAtPath("/Rack/Body")
    material, _ = UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()
    assert material and str(material.GetPath()) == "/Rack/_materials/M_Body"
    assert not any("/root" in str(t) for p in stage.Traverse() for r in p.GetRelationships() for t in r.GetTargets())
    assert not any("/root" in str(c) for p in stage.Traverse() for a in p.GetAttributes() for c in a.GetConnections())
