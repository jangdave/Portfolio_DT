"""서버 홀 내부 모델(랙, CRAC)이 같이 쓰는 도우미. `make_building_exterior.py`의 MB, Parts를 그대로 쓰고 아래만 더한다.

- 길이 단위는 cm다(건물 스크립트의 MB는 미터로 쓰고 100배 한다). `MB2.build()`는 곱하지 않고 그대로 저장한다.
- `cbox`: 모서리를 깎은(베벨) 상자. `poly`: 한 면. UV는 면의 큰 방향 기준 평면 투영(길이 / 타일 크기)이거나 직접 준 함수.
- 재질: 텍스처(기본색, 노멀, 거칠기, 금속성, 발광), 단색, 발광, 반투명.
- `place`: 부품(MB)을 종류별 그룹(빈 오브젝트 = USD Xform) 아래에 둔다.
"""
from __future__ import annotations

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_building_exterior as mbe  # noqa: E402
from make_building_exterior import MB, Parts, flat_material  # noqa: E402,F401
from make_rack_blockout import empty, setup_units  # noqa: E402,F401

HALL_TEX_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures", "hall"))
BLEND_DIR = os.path.dirname(os.path.dirname(HALL_TEX_DIR))  # .blend 파일이 있는 blender/ 폴더. 텍스처 경로를 여기 기준 상대 경로로 저장한다

class MB2(MB):
    """cm 단위 부품 메시. 면 하나, 모서리를 깎은 상자를 만든다."""

    def build(self, mats: dict, parent):  # MB.build와 같고 100배 곱하기만 뺀다
        me = bpy.data.meshes.new(self.name + "_mesh")
        me.from_pydata([tuple(v) for v in self.verts], [], [])
        me.polygons.add(len(self.counts))
        me.loops.add(len(self.loops))
        me.loops.foreach_set("vertex_index", self.loops)
        me.polygons.foreach_set("loop_start", self.starts)
        me.polygons.foreach_set("loop_total", self.counts)
        names: list[str] = []
        for m in self.mat:
            if m not in names:
                names.append(m)
        for n in names:
            me.materials.append(mats[n])
        me.polygons.foreach_set("material_index", [names.index(m) for m in self.mat])
        me.polygons.foreach_set("use_smooth", self.smooth)
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [c for p in self.uvs for c in p])
        me.update(calc_edges=True)
        me.validate(verbose=False)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = parent
        return ob

    def poly(self, pts, mat, hint, ts=100.0, uvo=(0.0, 0.0, 0.0), uvf=None, smooth=False):
        """점 목록으로 면 하나. hint(모양 중심) 바깥을 보게 순서를 맞춘다."""
        nx = ny = nz = 0.0
        for k in range(len(pts)):
            a, b = pts[k], pts[(k + 1) % len(pts)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        ax = max(range(3), key=lambda i: abs((nx, ny, nz)[i]))
        uvs = []
        for p in pts:
            if uvf is not None:
                uvs.append(uvf(ax, p))
            else:
                q = (p[0] + uvo[0], p[1] + uvo[1], p[2] + uvo[2])
                a2, b2 = {0: (q[1], q[2]), 1: (q[0], q[2]), 2: (q[0], q[1])}[ax]
                uvs.append((a2 / ts, b2 / ts))
        ids = self.vs(pts)
        self.face(ids, uvs, mat, hint, smooth=smooth)

    def cbox(self, c, s, mat, ch=0.0, ts=100.0, uvo=(0.0, 0.0, 0.0), skip=(), uvf=None):
        """중심 c, 크기 s(가로, 깊이, 높이)인 상자. ch > 0이면 모서리를 ch(cm)만큼 깎는다. skip: '-x','+y' 같은 면 이름."""
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        ch = min(ch, hx * 0.9, hy * 0.9, hz * 0.9)
        cx, cy, cz = c

        def P(x, y, z):
            return (cx + x, cy + y, cz + z)

        kw = dict(ts=ts, uvo=uvo, uvf=uvf)
        if ch <= 1e-6:
            for sx in (-1, 1):
                nm = "-x" if sx < 0 else "+x"
                if nm not in skip:
                    self.poly([P(sx * hx, a * hy, b * hz) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)
            for sy in (-1, 1):
                nm = "-y" if sy < 0 else "+y"
                if nm not in skip:
                    self.poly([P(a * hx, sy * hy, b * hz) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)
            for sz in (-1, 1):
                nm = "-z" if sz < 0 else "+z"
                if nm not in skip:
                    self.poly([P(a * hx, b * hy, sz * hz) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)
            return
        # 모서리를 깎은 상자: 면 6, 모서리 띠 12, 모서리 삼각형 8
        for sx in (-1, 1):
            if ("-x" if sx < 0 else "+x") not in skip:
                self.poly([P(sx * hx, a * (hy - ch), b * (hz - ch)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)
        for sy in (-1, 1):
            if ("-y" if sy < 0 else "+y") not in skip:
                self.poly([P(a * (hx - ch), sy * hy, b * (hz - ch)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)
        for sz in (-1, 1):
            if ("-z" if sz < 0 else "+z") not in skip:
                self.poly([P(a * (hx - ch), b * (hy - ch), sz * hz) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))], mat, c, **kw)

        def px(sx, sy, sz):
            return P(sx * hx, sy * (hy - ch), sz * (hz - ch))

        def py(sx, sy, sz):
            return P(sx * (hx - ch), sy * hy, sz * (hz - ch))

        def pz(sx, sy, sz):
            return P(sx * (hx - ch), sy * (hy - ch), sz * hz)

        for sx in (-1, 1):  # z 방향 모서리
            for sy in (-1, 1):
                self.poly([px(sx, sy, -1), py(sx, sy, -1), py(sx, sy, 1), px(sx, sy, 1)], mat, c, **kw)
        for sx in (-1, 1):  # y 방향 모서리
            for sz in (-1, 1):
                self.poly([px(sx, -1, sz), pz(sx, -1, sz), pz(sx, 1, sz), px(sx, 1, sz)], mat, c, **kw)
        for sy in (-1, 1):  # x 방향 모서리
            for sz in (-1, 1):
                self.poly([py(-1, sy, sz), pz(-1, sy, sz), pz(1, sy, sz), py(1, sy, sz)], mat, c, **kw)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    self.poly([px(sx, sy, sz), py(sx, sy, sz), pz(sx, sy, sz)], mat, c, **kw)


class Parts2(Parts):
    """Parts와 같고 MB2(cm 단위) 메시를 돌려준다."""

    def __call__(self, key: str) -> MB2:
        if key not in self.items:
            mb = MB2(f"{self.group}_{key}", group=self.group)
            self.items[key] = mb
            self.sink.append(mb)
        return self.items[key]


# --- 재질 ----------------------------------------------------------------------
def use_hall_textures() -> None:
    mbe.TEX_DIR = HALL_TEX_DIR


def tex_material(name, prefix, metallic=0.0, use_metal_map=False, emissive=None, emis_strength=1.0):
    """텍스처 재질(기본색, 노멀, 거칠기, 선택: 금속성, 발광). 단면이다."""
    mat = mbe.textured_material(name, prefix, BLEND_DIR, metallic, use_metal_map)
    if emissive:
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = mbe._img(emissive, "sRGB", BLEND_DIR)
        n.location = (-700, -900)
        nt.links.new(n.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emis_strength
    return mat


def emissive_material(name, rgb, strength):
    mat = flat_material(name, (0.02, 0.02, 0.02), 0.0, 0.6)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = strength
    return mat


def glass_material(name, rgb, alpha, roughness=0.1):
    mat = flat_material(name, rgb, 0.0, roughness, cull=False)
    mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = alpha
    return mat


def place(builders, mats, root, seen=None):
    """부품(MB)을 만들어 root 아래에 둔다. mb.group이 있으면 같은 이름의 빈 오브젝트(Xform)를 한 번만 만들어 그 아래에 둔다. 만든 오브젝트 사전을 돌려준다."""
    groups: dict = {} if seen is None else seen
    made = {}
    for mb in builders:
        if not mb.counts:
            continue
        parent = root
        if mb.group:
            if mb.group not in groups:
                groups[mb.group] = empty(mb.group, (0, 0, 0), root)
            parent = groups[mb.group]
        made[mb.name] = mb.build(mats, parent)
    return made


def add_anchors(parent, specs):
    """센서 앵커(빈 오브젝트). specs = [(metric, unit, y, z)]. 09 규격 4장: 이름 Sensor_<METRIC>, assetType=sensor, metric, unit."""
    anchors = empty("Anchors", (0, 0, 0), parent)
    for metric, unit, y, z in specs:
        a = empty(f"Sensor_{metric.upper()}", (0, y, z), anchors)
        a["assetType"] = "sensor"
        a["metric"] = metric
        a["unit"] = unit
    return anchors


def report(builders, label):
    total = 0
    for b in builders:
        total += b.triangles()
    print(f"{label} 삼각형 합계(MB 기준): {total}, 메시 {sum(1 for b in builders if b.counts)}개")
    return total
