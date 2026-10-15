"""check_coplanar_faces.py 테스트: 겹친 면은 찾고, 맞붙은 반대 방향 면과 떨어진 면은 세지 않는다."""
from __future__ import annotations

from pathlib import Path

from pxr import Usd, UsdGeom

from check_coplanar_faces import collect_faces, find_pairs


def make_box(stage, path, lo, hi):
    mesh = UsdGeom.Mesh.Define(stage, path)
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    mesh.GetPointsAttr().Set([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    mesh.GetFaceVertexCountsAttr().Set([4] * 6)
    # 바깥쪽을 향하는 법선(오른손 법칙)
    mesh.GetFaceVertexIndicesAttr().Set([0, 3, 2, 1, 4, 5, 6, 7, 0, 1, 5, 4, 2, 3, 7, 6, 1, 2, 6, 5, 3, 0, 4, 7])
    return mesh


def pairs_for(tmp_path: Path, boxes: list[tuple]) -> dict:
    stage = Usd.Stage.CreateNew(str(tmp_path / "t.usda"))
    for i, (lo, hi) in enumerate(boxes):
        make_box(stage, f"/B{i}", lo, hi)
    return find_pairs(collect_faces(stage, None, 1.0), tol=0.5, min_overlap=1.0)


def test_flush_tops_are_found(tmp_path):
    # 두 상자의 윗면이 같은 높이(z=10)에서 겹친다 -> 같은 방향 면이 같은 평면에 겹침
    found = pairs_for(tmp_path, [((0, 0, 0), (10, 10, 10)), ((5, 5, 5), (15, 15, 10))])
    assert any(v[2] == "Z" for v in found.values())


def test_touching_opposite_faces_are_not_counted(tmp_path):
    # 위 상자의 아랫면과 아래 상자의 윗면은 같은 평면이지만 법선이 반대다 -> 센 면은 없어야 한다
    found = pairs_for(tmp_path, [((0, 0, 0), (10, 10, 10)), ((0, 0, 10), (10, 10, 20))])
    assert not any(v[2] == "Z" for v in found.values())


def test_separated_faces_are_not_counted(tmp_path):
    found = pairs_for(tmp_path, [((0, 0, 0), (10, 10, 10)), ((0, 0, 20), (10, 10, 30))])
    assert found == {}


def test_small_depth_difference_still_counts(tmp_path):
    # 0.2 cm 차이도 깜빡일 수 있어 후보다
    found = pairs_for(tmp_path, [((0, 0, 0), (10, 10, 10)), ((2, 2, 0), (12, 12, 10.2))])
    assert any(v[2] == "Z" for v in found.values())


def test_triangle_fans_are_not_false_positives(tmp_path):
    # 한 원판을 삼각형 부채꼴로 쪼갠 면은 서로 맞닿을 뿐 겹치지 않는다(경계 상자만 겹침)
    stage = Usd.Stage.CreateNew(str(tmp_path / "fan.usda"))
    mesh = UsdGeom.Mesh.Define(stage, "/Disk")
    mesh.GetPointsAttr().Set([(0, 0, 5), (10, 0, 5), (10, 10, 5), (0, 10, 5), (5, 5, 5)])
    mesh.GetFaceVertexCountsAttr().Set([3, 3, 3, 3])
    mesh.GetFaceVertexIndicesAttr().Set([4, 0, 1, 4, 1, 2, 4, 2, 3, 4, 3, 0])
    assert find_pairs(collect_faces(stage, None, 1.0), tol=0.5, min_overlap=1.0) == {}
