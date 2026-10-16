"""CRAC(룸 에어컨) 상세 모델을 만든다(블록아웃 `make_crac_blockout.py`의 후속). 부품마다 메시 하나, 종류별 그룹(Xform)으로 묶는다.

실행 (저장소 루트에서, 텍스처를 먼저 준비한다):
    blender -b --factory-startup --python blender/scripts/make_crac_detailed.py -- blender/crac.blend

- 단위: 1 단위 = 1 cm. 바깥 크기 90 x 100 x 220 cm(블록아웃과 같다, 시뮬레이션이 읽는다). 원점은 바닥 중앙, 앞쪽(-Y)이 뜨거운 공기를 빨아들이는 회수면.
  튀어나온 것(손잡이, 표시창)은 이 상자 안쪽에 둔다.
- 구조 (CRAC 바로 아래):
    Base/(Plinth, Core)                     받침(바닥 10 cm)과 속(어두운 몸통)
    Side/(Panel_L_01~03, Panel_R_01~03)     옆 패널 3분할(틈 0.4 cm)
    Front/(Panel_Low, Panel_Up, Handle_L/R, Status)  앞 패널 위아래, 손잡이, 상태 표시창과 표시등
    Return/(Frame, Grille, Back)            회수 격자: 틀, 가로 살 28장, 뒤쪽 어두운 판
    Top/(Cover, Fan_Ring, Fan_Spokes, Fan_Hub)       상단 덮개와 팬 덮개
    Rear/(Panel_Up, Panel_Low_L/R, Supply_Frame, Supply_Grille, Supply_Back)  뒷면, 급기 개구부(찬 공기가 이중 바닥으로 나가는 곳)
    Anchors/Sensor_*                          센서 앵커(블록아웃과 같은 자리)
- 실제 제품을 따라 만들지 않은 가상 장비다. 글자, 로고 없음.
"""
from __future__ import annotations

import sys

import bpy

sys.path.insert(0, __file__.rsplit("make_crac_detailed.py", 1)[0])
import hall_parts as hp  # noqa: E402
from hall_parts import Parts2  # noqa: E402

CRAC_W, CRAC_D, CRAC_H = 90.0, 100.0, 220.0
TS = 100.0  # T_CracPaint 실제 크기(cm)
GAP = 0.4


def make_materials():
    hp.use_hall_textures()
    return {
        "M_CracBody": hp.tex_material("M_CracBody", "T_CracPaint", 0.4, False),
        "M_CracPlinth": hp.flat_material("M_CracPlinth", (0.10, 0.105, 0.11), 0.4, 0.6),
        "M_CracCore": hp.flat_material("M_CracCore", (0.015, 0.015, 0.018), 0.2, 0.8),
        "M_CracReturn": hp.flat_material("M_CracReturn", (0.05, 0.05, 0.06), 0.2, 0.7),  # 회수면 뒤판
        "M_CracGrille": hp.flat_material("M_CracGrille", (0.07, 0.075, 0.08), 0.7, 0.4),
        "M_CracTop": hp.flat_material("M_CracTop", (0.30, 0.32, 0.35), 0.5, 0.5),
        "M_CracSupply": hp.flat_material("M_CracSupply", (0.10, 0.35, 0.70), 0.2, 0.5),
        "M_CracHandle": hp.flat_material("M_CracHandle", (0.20, 0.21, 0.23), 0.8, 0.35),
        "M_CracDisplay": hp.emissive_material("M_CracDisplay", (0.10, 0.80, 0.70), 2.0),
        "M_CracLEDGreen": hp.emissive_material("M_CracLEDGreen", (0.1, 1.0, 0.25), 4.0),
        "M_CracLEDAmber": hp.emissive_material("M_CracLEDAmber", (1.0, 0.6, 0.1), 4.0),
    }


def ring(mb, x0, x1, y, t, z0, z1, bar, mat):
    """직사각형 틀(막대 4개). y는 중심, t는 두께."""
    xc, zc, w, h = (x0 + x1) / 2, (z0 + z1) / 2, x1 - x0, z1 - z0
    mb.cbox((xc, y, z1 - bar / 2), (w, t, bar), mat, ch=0.3, ts=TS)
    mb.cbox((xc, y, z0 + bar / 2), (w, t, bar), mat, ch=0.3, ts=TS)
    mb.cbox((x0 + bar / 2, y, zc), (bar, t, h - 2 * bar), mat, ch=0.3, ts=TS)
    mb.cbox((x1 - bar / 2, y, zc), (bar, t, h - 2 * bar), mat, ch=0.3, ts=TS)


def build_parts(objs):
    X = CRAC_W / 2 - 1.2  # 앞뒤 패널 가로 반폭 43.8
    YF, YR = -49.2, 49.0  # 앞 패널 바깥면, 뒤 패널 바깥면 (받침이 -50 ~ 50을 이미 차지한다)
    PT = 1.6  # 앞뒤 패널 두께
    z_lo, z_hi = 11.0, 216.0

    B = Parts2("Base", objs)
    B("Plinth").cbox((0, 0, 5.0), (CRAC_W, CRAC_D, 10.0), "M_CracPlinth", ch=0.5, ts=TS)
    B("Core").cbox((0, 0, 113.5), (86.0, 96.0, 207.0), "M_CracCore", ts=TS)

    S = Parts2("Side", objs)
    ys = [(-49.2, -16.6), (-16.2, 16.2), (16.6, 49.0)]
    for tag, sx in (("L", -1), ("R", 1)):
        for k, (ya, yb) in enumerate(ys, start=1):
            S(f"Panel_{tag}_{k:02d}").cbox((sx * 44.4, (ya + yb) / 2, (z_lo + z_hi) / 2), (1.2, yb - ya, z_hi - z_lo), "M_CracBody", ch=0.3, ts=TS)

    F = Parts2("Front", objs)
    F("Panel_Low").cbox((0, YF + PT / 2, (z_lo + 45.0) / 2), (2 * X, PT, 45.0 - z_lo), "M_CracBody", ch=0.3, ts=TS)
    F("Panel_Up").cbox((0, YF + PT / 2, (185.0 + z_hi) / 2), (2 * X, PT, z_hi - 185.0), "M_CracBody", ch=0.3, ts=TS)
    for tag, sx in (("L", -1), ("R", 1)):  # 세로 손잡이: 가장 앞쪽 y -49.9 (-50 안쪽)
        F(f"Handle_{tag}").cbox((sx * 30.0, YF - 0.35, 28.0), (2.0, 0.7, 12.0), "M_CracHandle", ch=0.2, ts=TS)
    st = F("Status")  # 상태 표시창(어두운 청록 발광)과 표시등 3개
    st.cbox((0, YF - 0.2, 201.0), (18.0, 1.0, 6.0), "M_CracDisplay", ts=TS)
    for i, (dx, m) in enumerate(((-30.0, "M_CracLEDGreen"), (-26.0, "M_CracLEDAmber"), (-22.0, "M_CracLEDGreen"))):
        st.cbox((dx, YF - 0.2, 201.0), (1.4, 1.0, 1.4), m, ts=TS)

    R = Parts2("Return", objs)  # 회수 격자(뜨거운 공기가 들어오는 앞면 큰 개구부)
    zg0, zg1 = 45.4, 184.6
    ring(R("Frame"), -X, X, YF + PT / 2, PT, zg0, zg1, 4.0, "M_CracBody")
    g = R("Grille")
    n = 28
    pitch = (zg1 - zg0 - 8.0) / n
    for k in range(n):
        g.cbox((0, YF + PT / 2, zg0 + 4.0 + pitch * (k + 0.5)), (2 * X - 8.0, PT, 1.0), "M_CracGrille", ch=0.15, ts=TS)
    R("Back").cbox((0, YF + PT + 0.4, (zg0 + zg1) / 2), (2 * X - 8.0, 0.4, zg1 - zg0 - 8.0), "M_CracReturn", ts=TS)

    T = Parts2("Top", objs)
    T("Cover").cbox((0, 0, 217.7), (CRAC_W, CRAC_D, 3.0), "M_CracTop", ch=0.5, ts=TS)  # z 216.2 ~ 219.2
    zt = 219.2
    T("Fan_Ring").tube((0, 0, zt), 24.0, 22.0, CRAC_H - zt, "M_CracGrille", seg=32, ts=TS)
    sp = T("Fan_Spokes")
    for sx in (-1, 1):
        sp.cbox((sx * 12.5, 0, zt + 0.4), (19.0, 1.0, 0.8), "M_CracGrille", ts=TS)
        sp.cbox((0, sx * 12.5, zt + 0.4), (1.0, 19.0, 0.8), "M_CracGrille", ts=TS)
    T("Fan_Hub").cyl((0, 0, zt), 3.0, CRAC_H - zt, "M_CracGrille", seg=16, ts=TS)

    Rr = Parts2("Rear", objs)
    yc = YR - PT / 2
    zs0, zs1, xs = 11.0, 84.0, 35.0  # 급기 개구부
    Rr("Panel_Up").cbox((0, yc, (zs1 + GAP + z_hi) / 2), (2 * X, PT, z_hi - zs1 - GAP), "M_CracBody", ch=0.3, ts=TS)
    for tag, sx in (("L", -1), ("R", 1)):
        a, b = xs + GAP, X
        Rr(f"Panel_Low_{tag}").cbox((sx * (a + b) / 2, yc, (zs0 + zs1) / 2), (b - a, PT, zs1 - zs0), "M_CracBody", ch=0.3, ts=TS)
    ring(Rr("Supply_Frame"), -xs, xs, yc, PT, zs0, zs1, 3.0, "M_CracSupply")
    sg = Rr("Supply_Grille")
    nv = 14
    pv = (2 * xs - 6.0) / nv
    for k in range(nv):
        sg.cbox((-xs + 3.0 + pv * (k + 0.5), yc, (zs0 + zs1) / 2), (1.0, PT, zs1 - zs0 - 6.0), "M_CracGrille", ch=0.15, ts=TS)
    Rr("Supply_Back").cbox((0, yc - PT / 2 - 0.4, (zs0 + zs1) / 2), (2 * xs - 6.0, 0.4, zs1 - zs0 - 6.0), "M_CracReturn", ts=TS)


def build() -> None:
    hp.setup_units()
    mats = make_materials()
    crac = hp.empty("CRAC", (0, 0, 0))
    crac["assetType"] = "crac"
    objs: list = []
    build_parts(objs)
    hp.place(objs, mats, crac)
    hp.add_anchors(crac, (
        ("supply_temp", "degC", CRAC_D / 2 + 5.0, 30.0),
        ("return_temp", "degC", -CRAC_D / 2 - 5.0, CRAC_H * 0.6),
        ("fan_speed", "percent", 0.0, CRAC_H + 5.0),
    ))
    for b in objs:
        print(f"  {b.name:24s} 삼각형 {b.triangles():6d}")
    hp.report(objs, "CRAC")
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            e = ob.evaluated_get(dg)
            me = e.to_mesh()
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            for v in me.vertices:
                w = ob.matrix_world @ v.co
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], w[i]), max(hi[i], w[i])
            e.to_mesh_clear()
    print("Blender가 센 삼각형 수:", n)
    print("경계 상자 최소", [round(v, 3) for v in lo], "최대", [round(v, 3) for v in hi])


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "crac.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("저장:", out)
