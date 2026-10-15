"""건물 외관용 4096x4096 PBR 텍스처를 직접 만든다 (절차적 생성, 외부 이미지 사용 없음).

실행 (저장소 루트에서, 파이썬 3.13 + numpy + pillow):
    uv run --python 3.13 --with numpy --with pillow python blender/scripts/make_building_textures.py
    (옵션) --out blender/textures/building   출력 폴더
    (옵션) --directx                          노멀 맵의 녹색 채널을 뒤집어(DirectX 규약) 만든다
    (옵션) --only panel,concrete              일부만 만든다

만드는 세트 (모두 타일링 가능, 같은 시드면 같은 결과):
    panel     외벽 금속 패널   타일 4.8 m (패널 폭 1.2 m x 높이 2.4 m, 4열 x 2행)  기본색, 노멀, 거칠기, 금속성, AO
    concrete  콘크리트         타일 4.0 m (줄눈 2.0 m 간격)                          기본색, 노멀, 거칠기
    asphalt   아스팔트         타일 4.0 m                                           기본색, 노멀, 거칠기
    roof      지붕 방수막      타일 4.8 m (이음 1.2 m 간격)                          기본색, 노멀, 거칠기

노멀 맵 규약: 기본은 OpenGL(녹색 = 위쪽이 +). Blender와 USD UsdPreviewSurface가 이 규약을 쓴다.
Unreal은 DirectX(녹색 = 아래쪽이 +)를 쓰므로 가져올 때 "Flip Green Channel"을 켜거나 --directx로 다시 만든다.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

N = 4096


# --- 도우미 -------------------------------------------------------------------
def pn(rng, beta: float, sx: float = 1.0, sy: float = 1.0, hi: float | None = None) -> np.ndarray:
    """이음새 없이 이어지는(주기적) 잡음. 평균 0, 표준편차 1.

    beta가 클수록 큰 덩어리, 0이면 흰 잡음. sx가 크면 x 방향으로 촘촘한 줄무늬(세로줄), sy가 크면 가로줄.
    hi가 있으면 그 주파수(타일당 주기 수) 위쪽을 부드럽게 잘라 낸다.
    """
    w = rng.standard_normal((N, N)).astype(np.float32)
    f = np.fft.rfft2(w)
    fy = (np.fft.fftfreq(N) * N)[:, None].astype(np.float32)
    fx = (np.fft.rfftfreq(N) * N)[None, :].astype(np.float32)
    r = np.sqrt((fx / sx) ** 2 + (fy / sy) ** 2)
    r[0, 0] = 1.0
    f *= r ** (-beta / 2.0)
    if hi is not None:
        f *= np.exp(-((np.sqrt(fx**2 + fy**2) / hi) ** 2))
    f[0, 0] = 0
    a = np.fft.irfft2(f, s=(N, N)).astype(np.float32)
    return (a - a.mean()) / (a.std() + 1e-9)


def grid(size_m: float):
    """픽셀 중심의 위치(미터). x는 오른쪽, y는 아래쪽으로 커진다. 모양 (1,N), (N,1)."""
    p = ((np.arange(N, dtype=np.float32) + 0.5) / N * size_m)
    return p[None, :], p[:, None]


def near_period(p: np.ndarray, period: float) -> np.ndarray:
    """가장 가까운 주기선(period의 배수)까지의 부호 있는 거리."""
    return ((p + period / 2) % period) - period / 2


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def normal_from_height(h_mm: np.ndarray, size_m: float, strength: float = 1.0, directx: bool = False) -> np.ndarray:
    """높이(mm)에서 접선 공간 노멀 맵(uint8 RGB)을 만든다. 가장자리는 반대편과 이어지게 계산한다."""
    mm_per_px = size_m * 1000.0 / N
    dx = (np.roll(h_mm, -1, axis=1) - np.roll(h_mm, 1, axis=1)) / (2 * mm_per_px)
    dy_down = (np.roll(h_mm, -1, axis=0) - np.roll(h_mm, 1, axis=0)) / (2 * mm_per_px)  # 아래쪽으로 커지는 기울기
    nx = -dx * strength
    ny_up = dy_down * strength  # 위쪽이 +인 녹색: 높이가 아래로 올라가면(dy_down>0) 면은 위쪽을 향한다
    nz = np.ones_like(nx)
    ln = np.sqrt(nx**2 + ny_up**2 + nz**2)
    nx, ny_up, nz = nx / ln, ny_up / ln, nz / ln
    g = -ny_up if directx else ny_up
    rgb = np.stack([nx, g, nz], axis=-1) * 0.5 + 0.5
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def save_rgb(path: Path, a: np.ndarray) -> None:
    """a: 0~1 실수 (N,N,3) 또는 uint8."""
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, "RGB").save(path, compress_level=6)


def save_gray(path: Path, a: np.ndarray) -> None:
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(path, compress_level=6)


def hash2(i: np.ndarray, j: np.ndarray, seed: int) -> np.ndarray:
    """정수 칸 번호로 0~1 난수를 만든다 (패널마다 색이 조금 다르게)."""
    h = (i.astype(np.int64) * 73856093) ^ (j.astype(np.int64) * 19349663) ^ (seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF).astype(np.float32) / 65535.0


# --- 외벽 금속 패널 -----------------------------------------------------------
def make_panel(out: Path, directx: bool) -> None:
    S = 4.8
    PW, PH = 1.2, 2.4  # 패널 폭, 높이(미터)
    rng = np.random.default_rng(1001)
    x, y = grid(S)
    dxs = near_period(x, PW)  # 가장 가까운 세로 이음선까지 거리(부호 있음)
    dys = near_period(y, PH)  # 가장 가까운 가로 이음선까지 거리
    seam = np.maximum(np.exp(-((dxs / 0.007) ** 2)), np.exp(-((dys / 0.007) ** 2)))  # 이음 홈 (폭 약 1.4 cm)
    seam_wide = np.maximum(np.exp(-((dxs / 0.03) ** 2)), np.exp(-((dys / 0.03) ** 2)))  # 이음 주변 그늘

    # 높이(mm): 가는 세로 골(리브), 이음 홈, 나사 머리
    ribs = 0.8 * np.sin(2 * np.pi * (x % PW) / 0.1) * smoothstep(0.02, 0.05, np.abs(dxs))
    dy_f = near_period(y, 0.6)
    screws = (np.hypot(np.abs(dxs) - 0.04, dy_f) < 0.007).astype(np.float32)
    screws = np.maximum(screws, 0)
    h = ribs - 3.0 * seam + 0.7 * screws + 0.15 * pn(rng, 0.0, hi=900)

    # 패널마다 색 차이
    pi = np.floor(x / PW).astype(np.int32) + 0 * y
    pj = np.floor(y / PH).astype(np.int32) + 0 * x
    tint = (hash2(pi, pj, 7) - 0.5) * 0.05

    # 오염: 위쪽 이음선 아래로 흘러내린 빗물 자국(세로줄) + 큰 얼룩
    streak = pn(rng, 2.2, sx=14.0, sy=0.45)
    blotch = pn(rng, 2.6, hi=60)
    t_down = (y % PH) / PH  # 위 이음선 0 → 아래 이음선 1
    runoff = np.clip(0.45 + 0.35 * streak, 0, 1) * (1 - t_down) ** 1.6
    grime_bottom = smoothstep(0.7, 1.0, t_down) * np.clip(0.4 + 0.3 * blotch, 0, 1) * 0.5
    dirt = np.clip(runoff * 0.75 + grime_bottom + 0.10 * blotch + 0.05 * seam_wide, 0, 1)

    base = np.array([0.66, 0.68, 0.70], dtype=np.float32)
    color = base[None, None, :] + tint[..., None]
    color = color * (1 - 0.42 * dirt[..., None])
    color = color + dirt[..., None] * np.array([0.02, 0.0, -0.025], dtype=np.float32)  # 살짝 누런 때
    color = color * (1 - 0.45 * seam[..., None])
    color = color * (1 - 0.15 * seam_wide[..., None])
    color = color + 0.012 * pn(rng, 0.0, hi=1500)[..., None]  # 미세한 거친 느낌

    rough = 0.42 + 0.33 * dirt + 0.04 * pn(rng, 1.0, hi=500) + 0.15 * seam
    metal = np.clip(0.55 - 0.4 * dirt - 0.3 * seam, 0, 1)
    ao = 1.0 - 0.75 * seam_wide * 0.9 - 0.5 * seam
    ao = ao - 0.04 * (np.abs(ribs) / 0.8)

    save_rgb(out / "T_BldgPanelMetal_BaseColor.png", color)
    save_rgb(out / "T_BldgPanelMetal_Normal.png", normal_from_height(h, S, 1.0, directx))
    save_gray(out / "T_BldgPanelMetal_Roughness.png", rough)
    save_gray(out / "T_BldgPanelMetal_Metallic.png", metal)
    save_gray(out / "T_BldgPanelMetal_AO.png", ao)


# --- 콘크리트 -----------------------------------------------------------------
def make_concrete(out: Path, directx: bool) -> None:
    S = 4.0
    rng = np.random.default_rng(2002)
    x, y = grid(S)
    dxs = near_period(x, 2.0)
    dys = near_period(y, 2.0)
    joint = np.maximum(np.exp(-((dxs / 0.006) ** 2)), np.exp(-((dys / 0.006) ** 2)))  # 줄눈(폭 약 1.2 cm)
    joint_wide = np.maximum(np.exp(-((dxs / 0.04) ** 2)), np.exp(-((dys / 0.04) ** 2)))

    blotch = pn(rng, 2.4, hi=80)
    mid = pn(rng, 1.4, hi=500)
    fine = pn(rng, 0.0, hi=1600)
    pits_src = pn(rng, 0.0, hi=1100)
    pits = smoothstep(2.4, 3.4, pits_src)  # 드문 구멍
    streak = pn(rng, 2.0, sx=10.0, sy=0.6)
    stain = np.clip(0.35 * streak + 0.25 * blotch, 0, 1) * 0.6

    h = 0.8 * mid + 0.35 * fine - 1.4 * pits - 4.0 * joint
    base = 0.50 + 0.035 * blotch + 0.02 * mid + 0.015 * fine
    base = base * (1 - 0.30 * pits) * (1 - 0.30 * stain) * (1 - 0.35 * joint) * (1 - 0.1 * joint_wide)
    color = np.stack([base * 1.0, base * 0.99, base * 0.96], axis=-1)
    rough = 0.80 + 0.06 * mid + 0.05 * fine - 0.05 * stain

    save_rgb(out / "T_BldgConcrete_BaseColor.png", color)
    save_rgb(out / "T_BldgConcrete_Normal.png", normal_from_height(h, S, 1.0, directx))
    save_gray(out / "T_BldgConcrete_Roughness.png", rough)


# --- 아스팔트 -----------------------------------------------------------------
def make_asphalt(out: Path, directx: bool) -> None:
    S = 4.0
    rng = np.random.default_rng(3003)
    mott = pn(rng, 2.5, hi=60)
    mid = pn(rng, 1.2, hi=600)
    flecks_src = pn(rng, 0.0, hi=1800)
    bumps = pn(rng, 0.0, hi=1300)
    flecks = smoothstep(1.6, 3.0, flecks_src)  # 밝은 자갈 알갱이

    # 갈라진 금이 있는 곳과 없는 곳
    ridge = pn(rng, 3.2, hi=200)
    area = smoothstep(0.2, 1.1, pn(rng, 3.0, hi=12))
    crack = np.exp(-((ridge / 0.045) ** 2)) * area

    h = 0.9 * bumps + 0.5 * mid - 2.5 * crack
    base = 0.17 + 0.02 * mott + 0.012 * mid + 0.02 * bumps + 0.14 * flecks
    base = base * (1 - 0.75 * crack)
    color = np.stack([base, base, base * 1.04], axis=-1)
    rough = 0.88 - 0.12 * flecks + 0.04 * mid - 0.05 * crack

    save_rgb(out / "T_Asphalt_BaseColor.png", color)
    save_rgb(out / "T_Asphalt_Normal.png", normal_from_height(h, S, 1.2, directx))
    save_gray(out / "T_Asphalt_Roughness.png", rough)


# --- 지붕 방수막 --------------------------------------------------------------
def make_roof(out: Path, directx: bool) -> None:
    S = 4.8
    rng = np.random.default_rng(4004)
    x, y = grid(S)
    dxs = near_period(x, 1.2)
    seam = np.exp(-((dxs / 0.012) ** 2))  # 방수막 이음(약간 솟은 선)
    seam_edge = np.exp(-((np.abs(dxs) - 0.03) / 0.008) ** 2)

    blotch = pn(rng, 2.6, hi=50)
    mid = pn(rng, 1.4, hi=500)
    fine = pn(rng, 0.0, hi=1700)
    puddle = smoothstep(0.3, 1.4, pn(rng, 3.0, hi=14))  # 물이 고여 때가 낀 곳
    dirt = np.clip(0.12 * blotch + 0.25 * puddle, 0, 1)

    h = 0.5 * seam + 0.25 * seam_edge + 0.25 * mid + 0.2 * fine
    base = 0.76 + 0.02 * blotch + 0.01 * mid + 0.008 * fine
    base = base * (1 - 0.32 * dirt)
    color = np.stack([base, base * 0.995, base * 0.97], axis=-1)
    color = color * (1 - 0.05 * seam_edge[..., None])
    rough = 0.62 + 0.15 * dirt + 0.04 * mid

    save_rgb(out / "T_BldgRoof_BaseColor.png", color)
    save_rgb(out / "T_BldgRoof_Normal.png", normal_from_height(h, S, 1.0, directx))
    save_gray(out / "T_BldgRoof_Roughness.png", rough)


SETS = {"panel": make_panel, "concrete": make_concrete, "asphalt": make_asphalt, "roof": make_roof}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="건물 외관 4K 텍스처 생성")
    ap.add_argument("--out", type=Path, default=Path("blender/textures/building"))
    ap.add_argument("--directx", action="store_true", help="노멀 맵 녹색 채널을 DirectX 규약으로")
    ap.add_argument("--only", default="", help="쉼표로 구분한 세트 이름")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    # 기본은 패널과 지붕만 만든다. 콘크리트와 아스팔트는 CC0 실사 텍스처(scripts/fetch_cc0_textures.py)를 쓴다.
    # 절차 생성 버전은 `--only concrete,asphalt`로 만들 수 있다(내려받을 수 없을 때의 대체용, 노멀이 거칠다).
    names = [n for n in args.only.split(",") if n] or ["panel", "roof"]
    for n in names:
        t = time.time()
        SETS[n](args.out, args.directx)
        print(f"{n}: {time.time() - t:.1f}초", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
