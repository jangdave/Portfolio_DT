"""번호가 연속인 시퀀스 폴더를 만든다. UE는 `이름_000.vdb, 이름_001.vdb ...` 연속 번호 파일을 한 애니메이션 볼륨으로 묶는다.

사용: python make_vdb_sequences.py <frames 폴더>   (입력: vdb_norm, vdb_norm_flipx, vdb_norm_flipy 안의 T_*.vdb)
"""
import shutil
import sys
from pathlib import Path

frames = Path(sys.argv[1])
for sub, prefix in (("vdb_norm", "TempN"), ("vdb_norm_flipx", "TempFX"), ("vdb_norm_flipy", "TempFY")):
    src = frames / sub
    dst = frames / f"{sub}_seq"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir()
    files = sorted(p for p in src.glob("T_*.vdb") if "_half" not in p.name)
    for i, f in enumerate(files):
        shutil.copy2(f, dst / f"{prefix}_{i:03d}.vdb")
    print(sub, len(files), "프레임 ->", dst)
