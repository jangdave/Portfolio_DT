"""건물 외관 미리보기 이미지를 만든다 (정면, 3/4, 옥상, 옥외 설비 근접, 난간 안쪽, 지면). 검수용이며 .blend는 저장하지 않는다.

실행 (저장소 루트에서):
    blender -b blender/building_exterior.blend --python blender/scripts/render_building_previews.py -- blender/previews [샘플수]
"""
from __future__ import annotations

import math
import sys

import bpy
from mathutils import Vector

M = 100.0
args = sys.argv[sys.argv.index("--") + 1:]
import os  # noqa: E402

OUT = os.path.abspath(args[0])  # 상대 경로면 Blender가 드라이브 루트에 저장하므로 절대 경로로 바꾼다
SAMPLES = int(args[1]) if len(args) > 1 else 24

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.eevee.taa_render_samples = SAMPLES
sc.view_settings.view_transform = "Standard"

# 하늘과 해
w = bpy.data.worlds.new("Sky")
w.use_nodes = True
nt = w.node_tree
bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
if not any(n.type == "OUTPUT_WORLD" for n in nt.nodes):
    nt.nodes.new("ShaderNodeOutputWorld")
out_n = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
nt.links.new(bg.outputs["Background"], out_n.inputs["Surface"])
bg.inputs["Color"].default_value = (0.55, 0.70, 0.90, 1)
bg.inputs["Strength"].default_value = 1.0
sc.world = w
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 4.0
sun.data.angle = math.radians(2)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
sc.collection.objects.link(sun)

# 부지 바깥 땅(미리보기 전용)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -30))
g = bpy.context.active_object
g.scale = (600 * M, 600 * M, 1)
gm = bpy.data.materials.new("PreviewGround")
gm.use_nodes = True
gb = gm.node_tree.nodes.get("Principled BSDF")
if gb is None:
    gb = gm.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    mo = next((n for n in gm.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or gm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    gm.node_tree.links.new(gb.outputs["BSDF"], mo.inputs["Surface"])
gb.inputs["Base Color"].default_value = (0.16, 0.26, 0.12, 1)
gb.inputs["Roughness"].default_value = 1.0
g.data.materials.append(gm)

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def shot(name, loc, target, lens=28.0):
    cam.location = Vector(loc) * M
    cam.data.lens = lens
    cam.data.clip_end = 1e6
    cam.data.clip_start = 20
    d = Vector(target) * M - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{OUT}/building_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("렌더:", sc.render.filepath)


shot("front", (0, -140, 14), (0, 0, 7), 28)
shot("three_quarter", (-115, -110, 55), (5, 0, 6), 30)
shot("roof", (-20, -30, 38), (5, 5, 15), 30)
shot("outdoor_close", (80, -42, 12), (50, 0, 3), 30)
shot("entrance", (14, -48, 5), (0, -23, 3.5), 30)
shot("generators", (-80, -38, 10), (-50, -2, 2.5), 30)
# 노이즈 점검용: 지붕 위에서 난간 안쪽 면(서쪽, 지붕 높이 z=14.4~15.4)을 낮은 각도로 본다
shot("roof_parapet", (-33.5, -20.5, 16.2), (-36, 20, 14.9), 28)
shot("roof_parapet_close", (-35.1, -17, 15.5), (-36, -8, 14.9), 35)
# 지면(아스팔트와 콘크리트 바닥판) 점검: 부지를 높은 곳에서 비스듬히 본다
shot("ground", (-20, -62, 14), (0, -35, 0), 30)
