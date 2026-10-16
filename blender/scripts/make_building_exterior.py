"""데이터센터 건물 외관(외벽, 지붕, 출입구, 환기구, 옥상 설비, 옥외 설비, 울타리)을 만든다.

실행 (저장소 루트에서):
    blender -b --factory-startup --python blender/scripts/make_building_exterior.py -- blender/building_exterior.blend

먼저 텍스처를 만들어 둔다 (`make_building_textures.py`, blender/textures/building/).

- 단위: Blender 1 단위 = 1 cm. 이 스크립트 안의 길이는 읽기 쉽게 **미터**로 쓰고 만들 때 100배 한다.
- 원점은 지면 중앙, 정문 쪽이 -Y, 위쪽이 +Z. 가상 건물이며 실제 시설, 상표, 간판 문구를 따라 하지 않았다.
- 구조 (09 규격 12장): Building(assetType=building, title) / Exterior / Floors / Outdoor(assetType=outdoor)
- 형상은 모두 진짜 지오메트리다. 오브젝트마다 점을 따로 만들어 붙이지 않고, 재질별 UV(텍셀 밀도 일정)를 넣는다.
  - 타일 크기: 패널 4.8 m, 지붕 4.8 m, 콘크리트 2.4 m, 아스팔트 2.5 m (텍스처 4096 px -> 850~1700 px/m). 콘크리트와 아스팔트는 CC0 실사 텍스처(실제 크기 기준)
- 만든 뒤 삼각형 수를 출력한다.
"""
from __future__ import annotations

import math
import os
import sys

import bpy

sys.path.insert(0, __file__.rsplit("make_building_exterior.py", 1)[0])
from make_rack_blockout import empty, setup_units  # noqa: E402  (랙 스크립트의 도우미를 그대로 쓴다)

M = 100.0  # 미터 -> Blender 단위(cm)
TEX_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures", "building"))

# --- 건물 크기 (미터). 근거 없이 정한 값: 아래 수치는 가상 건물 기준이다 ---
W, D = 72.0, 45.6  # 바닥 면적 (x, y). 패널 폭 1.2 m의 정수배(60칸, 38칸)
FH = 4.8  # 한 층 높이. 패널 높이 2.4 m의 2배
NF = 3
H = FH * NF  # 지붕 바닥면 높이 14.4
PAR = 1.0  # 난간벽 높이
PLINTH = 0.6  # 기초 높이
PW, PH = 1.2, 2.4  # 패널 크기
PD = 0.12  # 패널 두께
GAP = 0.02
TS_PANEL, TS_CONC, TS_ASPH, TS_ROOF = 4.8, 2.4, 2.5, 4.8  # 콘크리트와 아스팔트는 CC0 텍스처의 실제 크기(2.4 m, 2.5 m)

SITE_X0, SITE_X1, SITE_Y0, SITE_Y1 = -65.0, 65.0, -55.0, 50.0  # 울타리 안쪽 부지


# --- 재질 ----------------------------------------------------------------------
_images: dict[str, bpy.types.Image] = {}


def _img(name: str, colorspace: str, blend_dir: str):
    if name in _images:
        return _images[name]
    path = os.path.join(TEX_DIR, name)
    if not os.path.splitext(name)[1]:  # 확장자 없이 이름만 주면 .png, .jpg 순서로 찾는다 (CC0 텍스처는 jpg)
        for ext in (".png", ".jpg", ".jpeg"):
            if os.path.exists(path + ext):
                path += ext
                break
        else:
            raise FileNotFoundError(f"텍스처가 없다: {path}(.png/.jpg). make_building_textures.py와 scripts/fetch_cc0_textures.py를 먼저 실행한다")
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = colorspace
    try:
        im.filepath = bpy.path.relpath(path, start=blend_dir)
    except ValueError:
        pass
    _images[name] = im
    return im


def flat_material(name, rgb, metallic, roughness, cull=True):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = cull  # 뒷면을 그리지 않는다(같은 평면에 겹친 면이 뒤에서 비치는 것을 막음)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return mat


def textured_material(name, prefix, blend_dir, metallic=0.0, use_metal_map=False):
    """Principled BSDF 하나에 이미지 노드를 연결한다. (기본색, 노멀, 거칠기, 필요하면 금속성)"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Metallic"].default_value = metallic

    def tex(file, cs, x, y):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = _img(file, cs, blend_dir)
        n.interpolation = "Linear"
        n.extension = "REPEAT"
        n.location = (x, y)
        return n

    base = tex(f"{prefix}_BaseColor", "sRGB", -700, 300)
    nt.links.new(base.outputs["Color"], b.inputs["Base Color"])
    rough = tex(f"{prefix}_Roughness", "Non-Color", -700, 0)
    nt.links.new(rough.outputs["Color"], b.inputs["Roughness"])
    if use_metal_map:
        met = tex(f"{prefix}_Metallic", "Non-Color", -700, -300)
        nt.links.new(met.outputs["Color"], b.inputs["Metallic"])
    nrm_img = tex(f"{prefix}_Normal", "Non-Color", -700, -600)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (-350, -600)
    nt.links.new(nrm_img.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return mat


def make_materials(blend_dir: str) -> dict:
    return {
        "M_BldgPanelMetal": textured_material("M_BldgPanelMetal", "T_BldgPanelMetal", blend_dir, 0.4, True),
        "M_BldgConcrete": textured_material("M_BldgConcrete", "T_BldgConcrete", blend_dir),
        "M_BldgRoof": textured_material("M_BldgRoof", "T_BldgRoof", blend_dir),
        "M_Asphalt": textured_material("M_Asphalt", "T_Asphalt", blend_dir),
        "M_BldgGlass": flat_material("M_BldgGlass", (0.07, 0.12, 0.17), 0.0, 0.1, cull=False),
        # 외벽 유리: 반사 코팅 유리처럼 보이도록 금속성을 조금 주고 거칠기를 아주 낮춘다(불투명, 안쪽은 WallCore)
        "M_BldgCurtainGlass": flat_material("M_BldgCurtainGlass", (0.05, 0.11, 0.16), 0.55, 0.04),
        "M_BldgMullion": flat_material("M_BldgMullion", (0.16, 0.17, 0.18), 0.85, 0.40),
        "M_BldgLouver": flat_material("M_BldgLouver", (0.62, 0.64, 0.66), 0.85, 0.38),
        "M_BldgWallCore": flat_material("M_BldgWallCore", (0.05, 0.055, 0.06), 0.2, 0.7),
        "M_BldgFan": flat_material("M_BldgFan", (0.04, 0.045, 0.05), 0.5, 0.45),
        "M_BldgFloorProxy": flat_material("M_BldgFloorProxy", (0.35, 0.37, 0.40), 0.0, 0.8),
        "M_OutdoorEquip": flat_material("M_OutdoorEquip", (0.50, 0.55, 0.52), 0.5, 0.5),
        "M_Fence": flat_material("M_Fence", (0.55, 0.57, 0.58), 0.9, 0.45),
        "M_ParkingPaint": flat_material("M_ParkingPaint", (0.85, 0.85, 0.82), 0.0, 0.7),
        "M_Foliage": flat_material("M_Foliage", (0.10, 0.25, 0.08), 0.0, 0.85),
        "M_Trunk": flat_material("M_Trunk", (0.18, 0.12, 0.08), 0.0, 0.9),
    }


# --- 모양 만들기 도우미 --------------------------------------------------------
class MB:
    """재질 칸이 여러 개인 메시 하나를 모으는 도우미. 모든 길이는 미터."""

    def __init__(self, name: str, group: str = ""):
        self.name = name
        self.group = group  # 비어 있지 않으면 같은 이름의 빈 오브젝트 아래에 묶는다
        self.verts: list[tuple[float, float, float]] = []
        self.loops: list[int] = []
        self.starts: list[int] = []
        self.counts: list[int] = []
        self.uvs: list[tuple[float, float]] = []
        self.mat: list[str] = []
        self.smooth: list[bool] = []

    def vs(self, pts) -> list[int]:
        base = len(self.verts)
        self.verts.extend(pts)
        return list(range(base, base + len(pts)))

    def face(self, idx, uvs, mat, hint, inward=False, smooth=False):
        """면을 추가한다. hint(그 모양의 중심) 기준으로 바깥(또는 inward면 안쪽)을 보게 점 순서를 맞춘다."""
        p = [self.verts[i] for i in idx]
        nx = ny = nz = 0.0
        for k in range(len(p)):  # Newell 법선
            a, b = p[k], p[(k + 1) % len(p)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        cx = sum(q[0] for q in p) / len(p) - hint[0]
        cy = sum(q[1] for q in p) / len(p) - hint[1]
        cz = sum(q[2] for q in p) / len(p) - hint[2]
        d = nx * cx + ny * cy + nz * cz
        if (d < 0) != inward:
            idx = list(reversed(idx))
            uvs = list(reversed(uvs))
        self.starts.append(len(self.loops))
        self.counts.append(len(idx))
        self.loops.extend(idx)
        self.uvs.extend(uvs)
        self.mat.append(mat)
        self.smooth.append(smooth)

    # 상자. 크기 (sx, sy, sz), 중심 c. rot=(축, 각도(도)): 중심을 지나는 축으로 돌린다.
    def box(self, c, s, mat, ts=4.0, rot=None, uvo=(0.0, 0.0, 0.0), skip=()):
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        local = [(sx * hx, sy * hy, sz * hz) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
        # 모서리 번호: bit0=x, bit1=y, bit2=z (0이 -쪽)
        pre = [(c[0] + p[0], c[1] + p[1], c[2] + p[2]) for p in local]  # 돌리기 전 (UV용)
        pts = list(pre)
        if rot:
            axis, ang = rot
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            out = []
            for p in local:
                x, y, z = p
                if axis == "x":
                    y, z = y * ca - z * sa, y * sa + z * ca
                elif axis == "y":
                    x, z = x * ca + z * sa, -x * sa + z * ca
                else:
                    x, y = x * ca - y * sa, x * sa + y * ca
                out.append((c[0] + x, c[1] + y, c[2] + z))
            pts = out
        ids = self.vs(pts)
        # (이름, 모서리 4개)
        faces = {
            "-x": ((0, 2, 6, 4), "x"), "+x": ((1, 3, 7, 5), "x"),
            "-y": ((0, 1, 5, 4), "y"), "+y": ((2, 3, 7, 6), "y"),
            "-z": ((0, 1, 3, 2), "z"), "+z": ((4, 5, 7, 6), "z"),
        }
        for name, (corners, ax) in faces.items():
            if name in skip:
                continue
            uv = []
            for k in corners:
                px, py, pz = pre[k]
                px, py, pz = px + uvo[0], py + uvo[1], pz + uvo[2]
                a, b = {"x": (py, pz), "y": (px, pz), "z": (px, py)}[ax]
                uv.append((a / ts, b / ts))
            self.face([ids[k] for k in corners], uv, mat, c)

    def cyl(self, c, r0, h, mat, seg=24, axis="z", r1=None, caps=(True, True), ts=4.0):
        """원기둥/원뿔대. c는 아래쪽 면의 중심. 축 방향으로 높이 h."""
        r1 = r0 if r1 is None else r1

        def mp(a, b, t):
            if axis == "z":
                return (c[0] + a, c[1] + b, c[2] + t)
            if axis == "x":
                return (c[0] + t, c[1] + a, c[2] + b)
            return (c[0] + b, c[1] + t, c[2] + a)  # y

        mid = mp(0, 0, h / 2)
        ring0 = self.vs([mp(r0 * math.cos(2 * math.pi * i / seg), r0 * math.sin(2 * math.pi * i / seg), 0) for i in range(seg)])
        ring1 = self.vs([mp(r1 * math.cos(2 * math.pi * i / seg), r1 * math.sin(2 * math.pi * i / seg), h) for i in range(seg)])
        rm = (r0 + r1) / 2
        for i in range(seg):
            j = (i + 1) % seg
            u0, u1 = i / seg * 2 * math.pi * rm / ts, (i + 1) / seg * 2 * math.pi * rm / ts
            self.face([ring0[i], ring0[j], ring1[j], ring1[i]], [(u0, 0), (u1, 0), (u1, h / ts), (u0, h / ts)], mat, mid, smooth=True)
        for flag, rr, t in ((caps[0], r0, 0.0), (caps[1], r1, h)):
            if not flag:
                continue
            cen = self.vs([mp(0, 0, t)])[0]
            ring = self.vs([mp(rr * math.cos(2 * math.pi * i / seg), rr * math.sin(2 * math.pi * i / seg), t) for i in range(seg)])
            for i in range(seg):
                j = (i + 1) % seg
                a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * j / seg
                self.face(
                    [cen, ring[i], ring[j]],
                    [(0.5, 0.5), (0.5 + rr * math.cos(a0) / ts, 0.5 + rr * math.sin(a0) / ts), (0.5 + rr * math.cos(a1) / ts, 0.5 + rr * math.sin(a1) / ts)],
                    mat, mid)

    def tube(self, c, r_out, r_in, h, mat, seg=24, ts=4.0):
        """속이 빈 관(팬 둘레 테두리). 위, 아래 고리면 포함."""
        mid = (c[0], c[1], c[2] + h / 2)
        o0 = self.vs([(c[0] + r_out * math.cos(2 * math.pi * i / seg), c[1] + r_out * math.sin(2 * math.pi * i / seg), c[2]) for i in range(seg)])
        o1 = self.vs([(p[0], p[1], c[2] + h) for p in [self.verts[i] for i in o0]])
        i0 = self.vs([(c[0] + r_in * math.cos(2 * math.pi * i / seg), c[1] + r_in * math.sin(2 * math.pi * i / seg), c[2]) for i in range(seg)])
        i1 = self.vs([(p[0], p[1], c[2] + h) for p in [self.verts[i] for i in i0]])
        for i in range(seg):
            j = (i + 1) % seg
            uu = (i / seg * 2 * math.pi * r_out / ts, (i + 1) / seg * 2 * math.pi * r_out / ts)
            self.face([o0[i], o0[j], o1[j], o1[i]], [(uu[0], 0), (uu[1], 0), (uu[1], h / ts), (uu[0], h / ts)], mat, mid, smooth=True)
            self.face([i0[i], i0[j], i1[j], i1[i]], [(uu[0], 0), (uu[1], 0), (uu[1], h / ts), (uu[0], h / ts)], mat, mid, inward=True, smooth=True)
            for ring_o, ring_i in ((o1, i1), (o0, i0)):
                self.face([ring_o[i], ring_o[j], ring_i[j], ring_i[i]],
                          [(self.verts[ring_o[i]][0] / ts, self.verts[ring_o[i]][1] / ts), (self.verts[ring_o[j]][0] / ts, self.verts[ring_o[j]][1] / ts),
                           (self.verts[ring_i[j]][0] / ts, self.verts[ring_i[j]][1] / ts), (self.verts[ring_i[i]][0] / ts, self.verts[ring_i[i]][1] / ts)],
                          mat, mid)

    def sphere(self, c, r, mat, seg=10, rings=6, ts=4.0):
        grid = []
        for k in range(rings + 1):
            lat = math.pi * k / rings - math.pi / 2
            row = self.vs([(c[0] + r * math.cos(lat) * math.cos(2 * math.pi * i / seg), c[1] + r * math.cos(lat) * math.sin(2 * math.pi * i / seg), c[2] + r * math.sin(lat)) for i in range(seg)])
            grid.append(row)
        for k in range(rings):
            for i in range(seg):
                j = (i + 1) % seg
                idx = [grid[k][i], grid[k][j], grid[k + 1][j], grid[k + 1][i]]
                if k == 0:
                    idx = [grid[0][i], grid[1][j], grid[1][i]]
                elif k == rings - 1:
                    idx = [grid[k][i], grid[k][j], grid[k + 1][i]]
                uv = [(i / seg * 2 * math.pi * r / ts, k / rings * math.pi * r / ts)] * len(idx)
                self.face(idx, uv, mat, c, smooth=True)

    # --- 결과 ---
    def triangles(self) -> int:
        return sum(n - 2 for n in self.counts)

    def build(self, mats: dict, parent):
        me = bpy.data.meshes.new(self.name + "_mesh")
        me.from_pydata([(x * M, y * M, z * M) for x, y, z in self.verts], [], [])  # 점만 먼저
        # 면은 loop 배열로 직접 넣는다
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


class Parts:
    """같은 종류의 부품을 부품마다 메시 하나로 나눠서 만드는 도우미.

    `P = Parts("WallPanels", objs)` 뒤에 `P("South_F1")`을 부르면 이름이 `WallPanels_South_F1`인 메시(MB)를 돌려준다.
    같은 키를 다시 부르면 같은 메시를 돌려주고, 처음 부를 때만 objs에 등록한다. 그룹(WallPanels)은 USD에서 한 단계 위 prim이 된다.
    """

    def __init__(self, group: str, sink: list):
        self.group, self.sink, self.items = group, sink, {}

    def __call__(self, key: str) -> "MB":
        if key not in self.items:
            mb = MB(f"{self.group}_{key}", group=self.group)
            self.items[key] = mb
            self.sink.append(mb)
        return self.items[key]


FN = {"S": "South", "N": "North", "E": "East", "W": "West"}  # 벽 이름


def face_world(face, along, out, z):
    """벽면 기준 좌표(along: 벽을 따라, out: 바깥으로, z)를 월드 좌표로."""
    if face == "S":
        return (along, -D / 2 - out, z)
    if face == "N":
        return (along, D / 2 + out, z)
    if face == "E":
        return (W / 2 + out, along, z)
    return (-W / 2 - out, along, z)  # W


def wall_box(mb, face, along, out_c, z, s_along, s_out, s_z, mat, ts=4.0, tilt=0.0, uvo=(W / 2, D / 2, 0.0), skip=()):
    c = face_world(face, along, out_c, z)
    size = (s_along, s_out, s_z) if face in ("N", "S") else (s_out, s_along, s_z)
    rot = None
    if tilt:
        sign = {"S": 1, "N": -1, "E": 1, "W": -1}[face]
        rot = ("x" if face in ("N", "S") else "y", sign * tilt)
    mb.box(c, size, mat, ts, rot=rot, uvo=uvo, skip=skip)


# --- 구성 요소 ------------------------------------------------------------------
def wall_cells(face):
    return int(round((W if face in ("N", "S") else D) / PW))


def cell_center(face, i):
    total = W if face in ("N", "S") else D
    return -total / 2 + PW * (i + 0.5)


def row_z(k0, k1):
    z0 = max(k0 * PH, PLINTH)
    z1 = (k1 + 1) * PH
    return z0, z1


def louver_banks():
    """(벽, 시작 칸, 칸 수, 시작 행, 끝 행). 행 번호 k는 높이 2.4 m 단위."""
    out = []
    for face, starts in (("W", (2, 10, 18, 26, 34)), ("E", (2, 10, 18, 26, 34)), ("N", (6, 20, 34, 48))):
        for s in starts:
            if face == "N" and s in (20, 34):  # 뒤쪽(+Y) 가운데는 설비 반입구 자리
                pass
            for k0, k1 in ((0, 1), (2, 3), (4, 5)):
                out.append((face, s, 4, k0, k1))
    return out


def doors():
    """(벽, 칸) 작은 출입문. 바닥에서 2.4 m 이내(0행)에 있다."""
    return [("W", 22), ("E", 22), ("N", 14), ("N", 45)]


ENTRANCE = ("S", 27, 6, 0, 1)  # 정문: 앞쪽 가운데 6칸, 0~1행


def opening_mask() -> set:
    """패널을 빼는 칸 집합 {(벽, 칸, 행)}."""
    cut = set()
    for face, s, n, k0, k1 in louver_banks():
        for i in range(s, s + n):
            for k in range(k0, k1 + 1):
                cut.add((face, i, k))
    for face, i in doors():
        cut.add((face, i, 0))
    face, s, n, k0, k1 = ENTRANCE
    for i in range(s, s + n):
        for k in range(k0, k1 + 1):
            cut.add((face, i, k))
    return cut


def build_exterior(mats, parent):
    objs = []
    cut = opening_mask()

    # 기초(콘크리트 고리)
    pl = Parts("Plinth", objs)
    t = 0.15
    pl("South").box((0, -D / 2 - t / 2 + 0.05, PLINTH / 2), (W + 0.2, t + 0.1, PLINTH), "M_BldgConcrete", TS_CONC, skip=("-z",))
    pl("North").box((0, D / 2 + t / 2 - 0.05, PLINTH / 2), (W + 0.2, t + 0.1, PLINTH), "M_BldgConcrete", TS_CONC, skip=("-z",))
    pl("West").box((-W / 2 - t / 2 + 0.05, 0, PLINTH / 2), (t + 0.1, D - 0.0, PLINTH), "M_BldgConcrete", TS_CONC, skip=("-z",))
    pl("East").box((W / 2 + t / 2 - 0.05, 0, PLINTH / 2), (t + 0.1, D - 0.0, PLINTH), "M_BldgConcrete", TS_CONC, skip=("-z",))

    # 벽 속(어두운 안쪽 벽): 패널 틈이 어둡게 보이도록
    core = MB("WallCore")
    # 난간(지붕 위 1.0 m)은 패널만으로 만든다. 코어가 난간까지 올라가면 패널 안쪽 면과 같은 평면에 겹쳐 깜빡인다.
    core.box((0, 0, H / 2), (W - 2 * PD, D - 2 * PD, H), "M_BldgWallCore", TS_CONC, skip=("-z", "+z"))
    objs.append(core)

    # 외벽: 1~3층은 유리 커튼월(유리판 + 알루미늄 창틀), 난간만 금속 패널. 1.2 x 2.4 m 칸, 틈 2 cm. 뚫린 칸(루버, 문)은 건너뛴다.
    pan = Parts("WallPanels", objs)
    glz = Parts("CurtainGlass", objs)
    mul = Parts("Mullions", objs)
    nrows = int(round(H / PH))  # 6행. 7번째 행(난간벽)은 높이 1.0 m
    for face in "SNEW":
        for i in range(wall_cells(face)):
            a0 = -(W if face in "NS" else D) / 2 + PW * i + GAP / 2
            for k in range(nrows + 1):
                if (face, i, k) in cut:
                    continue
                z0 = max(k * PH, PLINTH) + GAP / 2
                z1 = (k + 1) * PH - GAP / 2 if k < nrows else H + PAR
                # 패널마다 텍스처를 패널 한 칸(1.2 x 2.4 m) 단위로 옮겨 같은 얼룩이 반복돼 보이지 않게 한다 (이음선 위치는 유지)
                rx, rz = (i * 7 + k * 3 + "SNEW".index(face)) % 4, (i * 5 + k) % 2
                part = f"F{k // 2 + 1}" if k < nrows else "Parapet"  # 층(2행 = 한 층)과 난간
                if k >= nrows:
                    wall_box(pan(f"{FN[face]}_{part}"), face, a0 + (PW - GAP) / 2, -PD / 2, (z0 + z1) / 2, PW - GAP, PD, z1 - z0, "M_BldgPanelMetal", TS_PANEL,
                             uvo=(W / 2 + rx * PW, D / 2 + rx * PW, rz * PH))
                    continue
                # 유리판: 바깥 면은 예전 패널 바깥 면(out = 0)과 같은 자리, 두께 3 cm
                wall_box(glz(f"{FN[face]}_{part}"), face, a0 + (PW - GAP) / 2, -0.015, (z0 + z1) / 2, PW - GAP, 0.03, z1 - z0, "M_BldgCurtainGlass")
                # 창틀: 칸의 왼쪽 세로 틀과 아래 가로 틀은 항상, 오른쪽과 위는 이웃 칸이 뚫렸거나 끝일 때만(겹쳐서 깜빡이지 않게 한 줄에 하나만)
                mn = mul(f"{FN[face]}_{part}")
                mw = 0.06
                wall_box(mn, face, a0 - GAP / 2, -0.04, (z0 + z1) / 2, mw, 0.12, z1 - z0 + GAP, "M_BldgMullion")
                if i == wall_cells(face) - 1 or (face, i + 1, k) in cut:
                    wall_box(mn, face, a0 + PW - GAP / 2, -0.04, (z0 + z1) / 2, mw, 0.12, z1 - z0 + GAP, "M_BldgMullion")
                # 가로 틀은 세로 틀보다 1 cm 더 튀어나오게 해서 겹치는 부분에서 같은 평면이 생기지 않게 한다
                wall_box(mn, face, a0 + (PW - GAP) / 2, -0.04, z1 + GAP / 2, PW - GAP, 0.14, mw, "M_BldgMullion")
                if k == 0:
                    wall_box(mn, face, a0 + (PW - GAP) / 2, -0.04, z0 - GAP / 2, PW - GAP, 0.14, mw, "M_BldgMullion")

    # 층 경계 띠(알루미늄) + 난간 덮개 + 모서리 기둥
    trim = Parts("WallTrim", objs)
    for face in "SNEW":
        L = W if face in "NS" else D
        for fi, z in enumerate((FH, 2 * FH), start=1):
            wall_box(trim(f"Band_{FN[face]}_{fi}"), face, 0, 0.03, z, L, 0.12, 0.14, "M_BldgLouver", skip=())
    for sx in (-1, 1):
        for sy in (-1, 1):
            # 모서리 기둥의 안쪽 면은 패널 두께(12 cm) 안쪽 3 cm에 묻는다(패널 안쪽 면과 같은 평면 근처에 두지 않음)
            trim(f"CornerPost_{'N' if sy > 0 else 'S'}{'E' if sx > 0 else 'W'}").box((sx * (W / 2 + 0.04), sy * (D / 2 + 0.04), (H + PAR) / 2 + PLINTH / 2), (0.26, 0.26, H + PAR - PLINTH), "M_BldgLouver")
    for nm, x, y, sx, sy in (("North", 0, D / 2 + 0.08, W + 0.4, 0.5), ("South", 0, -D / 2 - 0.08, W + 0.4, 0.5), ("East", W / 2 + 0.08, 0, 0.5, D + 0.4), ("West", -W / 2 - 0.08, 0, 0.5, D + 0.4)):
        trim(f"Coping_{nm}").box((x, y, H + PAR + 0.05), (sx, sy, 0.1), "M_BldgLouver")

    # 환기 루버 묶음
    lv = Parts("Louvers", objs)
    for face, s, n, k0, k1 in louver_banks():
        bank = lv(f"{FN[face]}_{s:02d}_R{k0 // 2 + 1}")  # 벽, 시작 칸, 층
        z0, z1 = row_z(k0, k1)
        zc, hh = (z0 + z1) / 2, z1 - z0 - GAP
        a0 = -(W if face in "NS" else D) / 2 + PW * s
        aw = PW * n - GAP
        ac = a0 + aw / 2 + GAP / 2
        # 뒷판(어두운 면)
        wall_box(bank, face, ac, -PD + 0.015, zc, aw, 0.03, hh, "M_BldgWallCore")
        # 테두리 4개
        fw = 0.10
        wall_box(bank, face, ac, -PD / 2 + 0.02, zc + hh / 2 - fw / 2, aw, PD + 0.04, fw, "M_BldgLouver")
        wall_box(bank, face, ac, -PD / 2 + 0.02, zc - hh / 2 + fw / 2, aw, PD + 0.04, fw, "M_BldgLouver")
        wall_box(bank, face, ac - aw / 2 + fw / 2, -PD / 2 + 0.02, zc, fw, PD + 0.04, hh - 2 * fw, "M_BldgLouver")
        wall_box(bank, face, ac + aw / 2 - fw / 2, -PD / 2 + 0.02, zc, fw, PD + 0.04, hh - 2 * fw, "M_BldgLouver")
        # 슬랫(기울어진 얇은 판)
        pitch = 0.09
        nsl = int((hh - 2 * fw) / pitch)
        for q in range(nsl):
            zq = zc - hh / 2 + fw + pitch * (q + 0.5)
            wall_box(bank, face, ac, -PD / 2 + 0.0, zq, aw - 2 * fw, 0.11, 0.015, "M_BldgLouver", tilt=38.0)

    # 작은 출입문(문짝, 계단, 차양)
    dr = Parts("ServiceDoors", objs)
    for face, i in doors():
        d_ = dr(f"{FN[face]}_{i:02d}")
        ac = cell_center(face, i)
        wall_box(d_, face, ac, -PD + 0.02, PLINTH + 1.05, 1.0, 0.04, 2.1, "M_BldgLouver")  # 문짝
        wall_box(d_, face, ac, -PD / 2 + 0.02, PLINTH + 2.15, 1.2, PD + 0.04, 0.1, "M_BldgLouver")  # 문 위 보
        wall_box(d_, face, ac - 0.55, -PD / 2 + 0.02, PLINTH + 1.05, 0.1, PD + 0.04, 2.1, "M_BldgLouver")
        wall_box(d_, face, ac + 0.55, -PD / 2 + 0.02, PLINTH + 1.05, 0.1, PD + 0.04, 2.1, "M_BldgLouver")
        wall_box(d_, face, ac, 0.9 + 0.1, PLINTH - 0.04, 2.0, 1.8, 0.04, "M_BldgConcrete", TS_CONC)  # 디딤판(윗면을 기초 윗면보다 2 cm 낮게)
        wall_box(d_, face, ac, 0.55, PLINTH + 2.6, 2.0, 1.1, 0.06, "M_BldgLouver")  # 작은 차양
        wall_box(d_, face, ac, -PD + 0.045, PLINTH + 1.05, 0.06, 0.02, 0.5, "M_BldgFan")  # 손잡이 자리

    # 정문: 유리벽, 문틀, 차양, 기둥, 앞 포장
    en = Parts("Entrance", objs)
    face, s, n, k0, k1 = ENTRANCE
    ew = n * PW - GAP
    z0, z1 = row_z(k0, k1)
    eh = z1 - z0
    en("Glass").box((0, -D / 2 - PD + 0.04, (z0 + z1) / 2), (ew, 0.04, eh), "M_BldgGlass")
    nm = 8
    for q in range(nm + 1):  # 세로 문틀
        x = -ew / 2 + ew * q / nm
        en("Frame").box((x, -D / 2 - PD / 2 + 0.04, (z0 + z1) / 2), (0.08, PD, eh), "M_BldgLouver")  # 바깥 면이 층 경계 띠보다 1 cm 안쪽
    for z in (z0 + 0.05, z0 + 2.4, z1 - 0.05):  # 가로 문틀
        en("Frame").box((0, -D / 2 - PD / 2 + 0.04, z), (ew, PD, 0.08), "M_BldgLouver")
    en("Canopy").box((0, -D / 2 - 1.8, FH + 0.15), (ew + 1.6, 3.8, 0.3), "M_BldgPanelMetal", TS_PANEL, uvo=(W / 2, D / 2, 0))  # 차양
    en("Canopy").box((0, -D / 2 - 1.8, FH + 0.32), (ew + 1.6, 3.8, 0.04), "M_BldgLouver")
    for x in (-ew / 2 + 0.4, ew / 2 - 0.4):
        en("Columns").cyl((x, -D / 2 - 3.3, 0.0), 0.18, FH, "M_BldgLouver", seg=16)  # 기둥
    en("Paving").box((0, -D / 2 - 2.0, 0.15), (ew + 3.0, 4.4, 0.3), "M_BldgConcrete", TS_CONC)  # 앞 포장
    for k in range(7):  # 볼라드
        en(f"Bollard_{k + 1:02d}").cyl((-ew / 2 - 1.0 + (ew + 2.0) * k / 6, -D / 2 - 5.2, 0.0), 0.12, 1.0, "M_BldgLouver", seg=12)

    # 지붕 바닥과 옥상 설비
    rf = MB("RoofDeck")
    # 지붕 바닥은 난간 패널 안쪽 면보다 1 cm씩 패널 속으로 넣는다(틈이 있으면 건물 속이 비쳐 보이고, 맞붙이면 옆면이 패널 안쪽 면과 같은 평면에 놓임).
    rf.box((0, 0, H + 0.05), (W - 2 * PD + 0.02, D - 2 * PD + 0.02, 0.1), "M_BldgRoof", TS_ROOF, skip=("-z",), uvo=(W / 2, D / 2, 0))
    objs.append(rf)

    re_ = Parts("RoofEquipment", objs)
    z_roof = H + 0.1
    chillers = []
    for row_y in (-9.0, 9.0):
        for i in range(10):
            chillers.append((-31.5 + 7.0 * i, row_y))
    for ci, (cx, cy) in enumerate(chillers, start=1):
        ch = re_(f"Chiller_{ci:02d}")
        ch.box((cx, cy, z_roof + 0.15), (6.4, 2.6, 0.3), "M_BldgLouver", skip=("-z",))  # 받침 틀
        ch.box((cx, cy, z_roof + 0.3 + 1.0), (6.0, 2.4, 2.0), "M_OutdoorEquip", skip=("-z",))  # 몸체
        for sy in (-1, 1):
            ch.box((cx, cy + sy * 1.22, z_roof + 1.3), (5.6, 0.04, 1.6), "M_BldgFan", skip=("-z",))  # 열교환 코일 면
        for q in (-1, 0, 1):
            fx = cx + q * 1.95
            ch.tube((fx, cy, z_roof + 2.3), 0.85, 0.78, 0.22, "M_BldgLouver", seg=24)
            ch.cyl((fx, cy, z_roof + 2.28), 0.2, 0.1, "M_BldgFan", seg=12, ts=1.0)  # 허브
            for b in range(6):  # 팬 날개
                ang = 60.0 * b
                bx, by = 0.42 * math.cos(math.radians(ang)), 0.42 * math.sin(math.radians(ang))
                ch.box((fx + bx, cy + by, z_roof + 2.36), (0.65, 0.16, 0.025), "M_BldgFan", rot=("z", ang + 20), ts=1.0)
            for r in (0.35, 0.6):  # 보호망 고리
                ch.tube((fx, cy, z_roof + 2.42), r + 0.012, r - 0.012, 0.02, "M_BldgLouver", seg=20)
    for i in range(8):  # 배기관
        st = re_(f"ExhaustStack_{i + 1:02d}")
        x = -28 + 8.0 * i
        st.cyl((x, 0.0, z_roof), 0.4, 3.2, "M_OutdoorEquip", seg=20)
        st.cyl((x, 0.0, z_roof + 3.2), 0.6, 0.15, "M_BldgLouver", seg=20)
    for si, (x, y, sx, sy, hh) in enumerate(((-30, 0, 6, 5, 3.6), (30, 0, 6, 5, 3.6), (0, 15.5, 8, 4, 2.6)), start=1):  # 계단실 2, 설비실 1
        hs = re_(("StairHouse_%02d" % si) if si < 3 else "MechRoom_01")
        hs.box((x, y, z_roof + hh / 2), (sx, sy, hh), "M_BldgPanelMetal", TS_PANEL, skip=("-z",), uvo=(W / 2, D / 2, 0))
        hs.box((x, y, z_roof + hh + 0.06), (sx + 0.3, sy + 0.3, 0.12), "M_BldgLouver")
    for ri, (x, y) in enumerate(((-34, -20), (34, -20), (-34, 20), (34, 20)), start=1):  # 피뢰침
        re_(f"LightningRod_{ri:02d}").cyl((x, y, z_roof), 0.05, 4.0, "M_BldgLouver", seg=8, ts=1.0)
    for z in (z_roof + 0.4,):  # 배관(가로)
        re_("RoofPipe_South").cyl((-31.5, -4.5, z), 0.18, 63.0, "M_BldgLouver", seg=12, axis="x")
        re_("RoofPipe_North").cyl((-31.5, 4.5, z), 0.18, 63.0, "M_BldgLouver", seg=12, axis="x")

    # 옥상 가림벽(루버 슬랫)
    sc = Parts("RoofScreens", objs)
    for y in (-12.5, 12.5):
        scr = sc("South" if y < 0 else "North")
        for i in range(0, 12):  # 기둥
            scr.box((-33.0 + 6.0 * i, y, z_roof + 1.6), (0.14, 0.14, 3.2), "M_BldgLouver", skip=("-z",))
        scr.box((0, y, z_roof + 3.2), (66.2, 0.14, 0.12), "M_BldgLouver")
        for q in range(int(2.8 / 0.12)):
            scr.box((0, y, z_roof + 0.3 + 0.12 * q), (66.0, 0.1, 0.02), "M_BldgLouver", rot=("x", 35.0))
    return objs


def build_floors(mats, parent):
    """층 표시용 단순 모양. 외벽 안쪽에 들어가며 바깥에서 보이지 않는다."""
    out = []
    for f in range(1, NF + 1):
        mb = MB(f"Floor_{f:02d}")
        z0, z1 = (f - 1) * FH + 0.15, f * FH - 0.15
        if f == 1:
            z0 = PLINTH
        mb.box((0, 0, (z0 + z1) / 2), (W - 1.2, D - 1.2, z1 - z0), "M_BldgFloorProxy", TS_CONC)
        out.append((mb, f))
    return out


def build_outdoor(mats, parent):
    out: list[MB] = []

    # 부지 바닥: 아스팔트 + 건물 둘레 콘크리트 + 주차선
    gr = Parts("SiteGround", out)
    sx, sy = SITE_X1 - SITE_X0, SITE_Y1 - SITE_Y0
    gr("Asphalt").box(((SITE_X0 + SITE_X1) / 2, (SITE_Y0 + SITE_Y1) / 2, -0.1), (sx, sy, 0.2), "M_Asphalt", TS_ASPH, skip=("-z",), uvo=(SITE_X1, SITE_Y1, 0))
    gr("Pavement_Building").box((0, 0, 0.01), (W + 12, D + 12, 0.02), "M_BldgConcrete", TS_CONC, skip=("-z",), uvo=(W / 2 + 6, D / 2 + 6, 0))  # 건물 둘레 포장
    gr("Walkway_Entrance").box((4.5, -39.0, 0.015), (3.0, 32.0, 0.03), "M_BldgConcrete", TS_CONC, skip=("-z",), uvo=(0, 0, 0))  # 정문 보도
    # 설비 바닥판
    for name, cx, cy, wx, wy in (("CoolingTowers", 50, 2.5, 20, 48), ("Generators", -50, -2, 17, 46), ("Substation", 0, 38, 40, 20), ("FuelTanks", -61.0, 1, 5, 28)):  # 연료 탱크 바닥판은 발전기 바닥판(x -58.5 ~ -41.5)과 겹치지 않게 x -63.5 ~ -58.5
        gr(f"Pad_{name}").box((cx, cy, 0.03), (wx, wy, 0.06), "M_BldgConcrete", TS_CONC, skip=("-z",), uvo=(cx, cy, 0))
    # 주차선
    for side in (-1, 1):
        for row_y in (-47.0, -36.0, -35.0, -24.5):
            pass
        for y0 in (-47.5, -36.5):
            for q in range(18):
                x = side * (9.0 + 2.7 * q)
                gr(f"ParkingLines_{'East' if side > 0 else 'West'}").box((x, y0 + 2.5, 0.025), (0.12, 5.0, 0.01), "M_ParkingPaint", 1.0, skip=("-z",))
        for y0 in (-35.0,):
            pass
    # 횡단보도
    for q in range(8):
        gr("Crosswalk").box((-2.1 + 0.6 * q, -D / 2 - 8.0, 0.025), (0.35, 3.0, 0.01), "M_ParkingPaint", 1.0, skip=("-z",))
    # 주차 구역 끝 연석(콘크리트)
    for side in (-1, 1):
        gr(f"Curb_{'East' if side > 0 else 'West'}").box((side * 32.0, -22.8 - 6.6, 0.08), (56.0, 0.3, 0.16), "M_BldgConcrete", TS_CONC)

    # 냉각탑 4기
    towers = []
    for i in range(4):
        mb = MB(f"CoolingTower_{i + 1:02d}", group="CoolingTowers")
        cx, cy = 50.0, -17.0 + 11.0 * i
        mb.box((cx, cy, 0.75), (9.4, 9.4, 1.5), "M_BldgConcrete", TS_CONC, skip=("-z",))  # 수조
        mb.box((cx, cy, 1.5 + 3.0), (8.6, 8.6, 6.0), "M_OutdoorEquip", skip=("-z",))  # 본체
        for face in range(4):  # 흡입 루버 면
            for q in range(24):
                zq = 2.0 + 0.2 * q
                ang = 90 * face
                ox, oy = (4.35 * math.cos(math.radians(ang)), 4.35 * math.sin(math.radians(ang)))
                size = (0.16, 8.0, 0.025) if face % 2 == 0 else (8.0, 0.16, 0.025)
                mb.box((cx + ox, cy + oy, zq), size, "M_BldgLouver", rot=("y" if face % 2 == 0 else "x", 35 if face in (0, 3) else -35), ts=1.0)
        mb.box((cx, cy, 7.5 + 0.1), (8.8, 8.8, 0.2), "M_BldgLouver")  # 윗덮개 테두리
        mb.cyl((cx, cy, 7.7), 3.3, 1.8, "M_OutdoorEquip", seg=40, r1=2.9, caps=(False, False))  # 팬 굴뚝
        mb.tube((cx, cy, 9.5), 2.9, 2.8, 0.15, "M_BldgLouver", seg=40)
        mb.cyl((cx, cy, 7.9), 0.45, 1.0, "M_BldgFan", seg=16, ts=1.0)
        for b in range(8):
            ang = 45.0 * b
            mb.box((cx + 1.5 * math.cos(math.radians(ang)), cy + 1.5 * math.sin(math.radians(ang)), 8.55), (2.4, 0.4, 0.05), "M_BldgFan", rot=("z", ang + 15), ts=1.0)
        for q in range(8):  # 사다리
            mb.box((cx + 4.5, cy - 4.0 + 0.0, 1.5 + 0.7 * q + 0.35), (0.06, 0.5, 0.05), "M_BldgLouver", ts=1.0)
        mb.box((cx + 4.42, cy - 4.25, 4.0), (0.05, 0.05, 5.0), "M_BldgLouver", ts=1.0)
        mb.box((cx + 4.42, cy - 3.75, 4.0), (0.05, 0.05, 5.0), "M_BldgLouver", ts=1.0)
        mb.cyl((cx - 5.4, cy, 0.5), 0.45, 4.0, "M_BldgLouver", seg=16, axis="x")  # 배관 가지
        towers.append(mb)
    pipe = MB("CoolingPipes", group="CoolingTowers")
    pipe.cyl((43.0, -20.0, 0.9), 0.5, 46.0, "M_BldgLouver", seg=20, axis="y")
    pipe.cyl((41.5, -20.0, 0.9), 0.5, 46.0, "M_OutdoorEquip", seg=20, axis="y")
    pipe.cyl((41.5, 24.0, 0.9), 0.5, 4.0, "M_OutdoorEquip", seg=20, axis="x")
    out.extend(towers)
    out.append(pipe)

    # 발전기 8대(컨테이너형). 긴 쪽이 X 방향이고 Y 방향으로 나란히 놓는다. 바깥(-X)쪽 끝이 공기 흡입면
    for i in range(8):
        mb = MB(f"Generator_{i + 1:02d}", group="Generators")
        cx, cy = -49.5, -20.0 + 5.2 * i
        mb.box((cx, cy, 0.4), (12.4, 3.2, 0.8), "M_OutdoorEquip", skip=("-z",))  # 연료 받침 탱크
        mb.box((cx, cy, 0.8 + 1.6), (12.2, 3.0, 3.2), "M_OutdoorEquip", skip=("-z",))  # 컨테이너
        for k in range(5):  # 옆면 세로 보강
            for sy in (-1, 1):
                mb.box((cx - 5.0 + 2.5 * k, cy + sy * 1.52, 2.4), (0.12, 0.06, 3.2), "M_BldgLouver", ts=1.0)
        mb.box((cx - 6.12, cy, 2.4), (0.03, 2.6, 2.4), "M_BldgFan", ts=1.0)  # 흡기 면(어두운 안쪽)
        for q in range(14):  # 흡기 루버
            mb.box((cx - 6.17, cy, 1.3 + 0.16 * q), (0.14, 2.6, 0.02), "M_BldgLouver", rot=("y", -35), ts=1.0)
        mb.cyl((cx + 4.5, cy, 4.0), 0.28, 3.2, "M_BldgFan", seg=16, ts=1.0)  # 배기관
        mb.cyl((cx + 4.5, cy, 7.2), 0.38, 0.1, "M_BldgLouver", seg=16, ts=1.0)
        mb.box((cx + 4.5, cy, 4.05), (1.2, 1.2, 0.1), "M_BldgLouver")  # 배기관 받침
        mb.box((cx + 1.0, cy - 1.52, 1.9), (1.0, 0.06, 2.1), "M_BldgLouver", ts=1.0)  # 점검문
        out.append(mb)

    # 연료 탱크 2기
    for ti, y in enumerate((-8.0, 10.0), start=1):
        fu = MB(f"FuelTank_{ti:02d}", group="FuelTanks")
        fu.cyl((-60.0, y - 5.0, 1.9), 1.6, 10.0, "M_OutdoorEquip", seg=32, axis="y", ts=4.0)
        for yy in (-3.0, 3.0):
            fu.box((-60.0, y + yy, 0.9), (3.4, 0.4, 1.8), "M_BldgConcrete", TS_CONC)
        fu.cyl((-60.0, y, 3.4), 0.35, 0.5, "M_BldgLouver", seg=12, ts=1.0)
        out.append(fu)

    # 변전 설비
    for i in range(4):
        sb = MB(f"Transformer_{i + 1:02d}", group="Substation")
        cx, cy = -13.5 + 9.0 * i, 40.0
        sb.box((cx, cy, 0.3), (5.6, 3.8, 0.6), "M_BldgConcrete", TS_CONC)
        sb.box((cx, cy, 0.6 + 1.7), (4.4, 2.6, 3.4), "M_OutdoorEquip", skip=("-z",))
        for q in range(14):  # 방열 핀
            for sy in (-1, 1):
                sb.box((cx - 1.95 + 0.3 * q, cy + sy * 1.55, 2.3), (0.05, 0.5, 2.8), "M_OutdoorEquip", ts=1.0)
        for q in (-1, 0, 1):  # 애자(고압 연결부)
            sb.cyl((cx + q * 1.1, cy, 4.0), 0.14, 1.2, "M_BldgWallCore", seg=12, ts=1.0)
            for r in range(4):
                sb.cyl((cx + q * 1.1, cy, 4.2 + 0.25 * r), 0.24, 0.06, "M_BldgWallCore", seg=12, ts=1.0)
        out.append(sb)
    sb = MB("Gantry", group="Substation")
    for x in (-18, 18):  # 문형 철골
        for dy in (-3, 3):
            sb.box((x, 33.0 + dy, 4.0), (0.4, 0.4, 8.0), "M_Fence", ts=1.0)
    sb.box((0, 30.0, 7.8), (36.8, 0.4, 0.4), "M_Fence", ts=1.0)
    sb.box((0, 36.0, 7.8), (36.8, 0.4, 0.4), "M_Fence", ts=1.0)
    for x in (-18, -9, 0, 9, 18):
        sb.box((x, 33.0, 7.8), (0.3, 6.0, 0.3), "M_Fence", ts=1.0)
    out.append(sb)

    # 울타리 (기둥 3 m 간격 + 가로대 + 세로 창살). 정문은 가운데 12 m를 문으로 쓴다.
    fe = Parts("Fence", out)
    FH_ = 2.4

    def fence_run(p0, p1, nm):
        part = fe(nm)
        (x0, y0), (x1, y1) = p0, p1
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(round(L / 3.0)))
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        ang = math.degrees(math.atan2(uy, ux))
        for q in range(n + 1):
            part.box((x0 + ux * L * q / n, y0 + uy * L * q / n, FH_ / 2), (0.1, 0.1, FH_ + 0.1), "M_Fence", 1.0, rot=("z", ang), skip=("-z",))
        for zc in (0.25, FH_ - 0.2):  # 아래, 위 가로대
            part.box(((x0 + x1) / 2, (y0 + y1) / 2, zc), (L, 0.05, 0.06), "M_Fence", 1.0, rot=("z", ang))
        nb = int(L / 0.14)
        for q in range(nb):  # 창살
            t = (q + 0.5) / nb * L
            part.box((x0 + ux * t, y0 + uy * t, FH_ / 2 + 0.03), (0.025, 0.025, FH_ - 0.1), "M_Fence", 1.0, rot=("z", ang), skip=("-z",))

    corners = [(SITE_X0, SITE_Y0), (SITE_X1, SITE_Y0), (SITE_X1, SITE_Y1), (SITE_X0, SITE_Y1)]
    fence_run((SITE_X0, SITE_Y0), (-6.0, SITE_Y0), "South_West")
    fence_run((6.0, SITE_Y0), (SITE_X1, SITE_Y0), "South_East")
    fence_run((SITE_X1, SITE_Y0), (SITE_X1, SITE_Y1), "East")
    fence_run((SITE_X1, SITE_Y1), (SITE_X0, SITE_Y1), "North")
    fence_run((SITE_X0, SITE_Y1), (SITE_X0, SITE_Y0), "West")

    gt = Parts("GateAndGuardHouse", out)
    for x in (-6.0, 6.0):  # 문 기둥
        gt("Posts").box((x, SITE_Y0, 1.5), (0.5, 0.5, 3.0), "M_BldgConcrete", TS_CONC, skip=("-z",))
    for sgn in (-1, 1):  # 미닫이 문 두 짝(닫힘). 아래 레일 + 가로대 + 창살
        x0, x1 = (0.0, sgn * 5.7)
        xc = (x0 + x1) / 2
        gt(f"Leaf_{'East' if sgn > 0 else 'West'}").box((xc, SITE_Y0 - 0.15, 2.1), (5.7, 0.06, 0.08), "M_Fence", 1.0)
        gt(f"Leaf_{'East' if sgn > 0 else 'West'}").box((xc, SITE_Y0 - 0.15, 0.3), (5.7, 0.06, 0.08), "M_Fence", 1.0)
        for q in range(int(5.7 / 0.12)):
            gt(f"Leaf_{'East' if sgn > 0 else 'West'}").box((x0 + sgn * 0.12 * (q + 0.5), SITE_Y0 - 0.15, 1.2), (0.03, 0.03, 1.9), "M_Fence", 1.0)
    gt("Rail").box((0, SITE_Y0, 0.02), (12.0, 0.2, 0.04), "M_BldgConcrete", TS_CONC)  # 레일 받침
    gt("GuardHouse").box((-10.0, SITE_Y0 + 5.0, 1.5 + 0.1), (4.0, 3.0, 3.0), "M_BldgPanelMetal", TS_PANEL, skip=("-z",))  # 경비실
    gt("GuardHouse").box((-10.0, SITE_Y0 + 5.0, 3.2), (4.8, 3.8, 0.2), "M_BldgLouver")
    gt("GuardHouse").box((-10.0, SITE_Y0 + 3.48, 1.9), (3.2, 0.04, 1.2), "M_BldgGlass")  # 정문 쪽 창
    gt("GuardHouse").box((-8.0 + 0.0, SITE_Y0 + 5.0, 1.9), (0.04, 2.2, 1.2), "M_BldgGlass")
    gt("Barrier").cyl((-6.8, SITE_Y0 + 8.0, 0.0), 0.2, 1.1, "M_BldgLouver", seg=12)  # 차단기 기둥
    gt("Barrier").box((-3.4, SITE_Y0 + 8.0, 1.0), (6.4, 0.1, 0.1), "M_ParkingPaint", 1.0)  # 차단봉

    # 조명 기둥
    nli = 0
    for side in (-1, 1):
        for q in range(6):
            nli += 1
            li = MB(f"LightPole_{nli:02d}", group="LightPoles")
            x = side * (10.0 + 9.0 * q)
            li.cyl((x, -34.0, 0.0), 0.12, 9.0, "M_Fence", seg=12, ts=1.0)
            li.box((x + 0.0, -34.0 + 0.5, 9.1), (0.5, 1.2, 0.12), "M_BldgFan", ts=1.0)
            out.append(li)

    # 조경: 산울타리, 나무
    ls = Parts("Landscape", out)
    for side in (-1, 1):
        ls(f"Hedge_{'East' if side > 0 else 'West'}").box((side * 21.0, -D / 2 - 3.5, 0.6), (29.0, 1.4, 1.2), "M_Foliage", 1.0, skip=("-z",))
    nt = 0
    for q in range(5):
        for side in (-1, 1):
            nt += 1
            tr = ls(f"Tree_{nt:02d}")
            x = side * (14.0 + 11.0 * q)
            y = SITE_Y0 + 3.0
            tr.cyl((x, y, 0.0), 0.22, 3.4, "M_Trunk", seg=10, ts=1.0)
            tr.sphere((x, y, 4.6), 2.2, "M_Foliage", seg=12, rings=8, ts=2.0)
            tr.sphere((x + 0.7, y + 0.4, 5.3), 1.5, "M_Foliage", seg=10, rings=6, ts=2.0)
    return out


def tri_report(builders):
    total = 0
    for b in builders:
        n = b.triangles()
        total += n
        print(f"  {b.name:24s} 삼각형 {n:8d}")
    print(f"삼각형 합계: {total}")
    return total


def build(blend_path: str) -> None:
    setup_units()
    blend_dir = os.path.dirname(os.path.abspath(blend_path))
    mats = make_materials(blend_dir)

    building = empty("Building", (0, 0, 0))
    building["assetType"] = "building"
    building["title"] = "Data Center Building"  # 화면 표시 이름(가상 시설). 장면에서 바꿔 쓴다.
    ex = empty("Exterior", (0, 0, 0), building)
    fl = empty("Floors", (0, 0, 0), building)
    od = empty("Outdoor", (0, 0, 0), building)
    od["assetType"] = "outdoor"

    groups: dict = {}

    def parent_of(mb, base):
        """mb.group이 있으면 같은 이름의 빈 오브젝트(Xform)를 base 아래에 만들어 그 아래로 보낸다."""
        if not mb.group:
            return base
        key = (base.name, mb.group)
        if key not in groups:
            g = empty(mb.group, (0, 0, 0), base)
            if base is od:
                g["assetType"] = "outdoor"
            groups[key] = g
        return groups[key]

    allb: list[MB] = []
    for mb in build_exterior(mats, ex):
        if mb.counts:
            mb.build(mats, parent_of(mb, ex))
            allb.append(mb)
    for mb, f in build_floors(mats, fl):
        ob = mb.build(mats, fl)
        ob["floor"] = f
        allb.append(mb)
    for mb in build_outdoor(mats, od):
        if mb.counts:
            ob = mb.build(mats, parent_of(mb, od))
            ob["assetType"] = "outdoor"
            allb.append(mb)
    tri_report(allb)
    # 메시를 Blender에 맡겨 통계 확인
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            me = ob.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            total += len(me.loop_triangles)
            ob.evaluated_get(dg).to_mesh_clear()
    print("Blender가 센 삼각형 수:", total)
    print("오브젝트 수:", sum(1 for o in bpy.data.objects if o.type == "MESH"))


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "building_exterior.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("저장:", out)
