"""학습 데이터 확장 계산을 두 단계로 이어서 돌린다(Windows에서 분리 실행: pythonw 또는 Start-Process -WindowStyle Hidden).

1단계: samples.json에서 아직 안 끝난 샘플(새 s41~s60, 이전에 실패한 s38, s40)을 계산한다.
2단계: 1단계가 끝나면 반복 3500회에 수렴하지 못했던 9개를 진행 기록에서 지우고 5500회 한도의 사례로 다시 계산한다
       (사례 정의는 make_cases.py --iters 5500으로 미리 다시 만들어 두었다).
각 단계는 keepalive.py가 WSL을 깨워 두면서 run_batch.py를 돌린다. 로그: expand.log
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROG = HERE.parent / "results" / "surrogate" / "progress.json"
LOG = HERE / "expand.log"
RERUN = ["s15_same_aisle_two_off", "s19_same_aisle_two_off", "s23_diff_aisle_two_off", "s24_diff_aisle_two_off", "s25_diff_aisle_two_off",
         "s32_fan_derated", "s34_fan_derated", "s36_remove_and_fail", "s37_remove_and_fail"]


def w(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def finished():
    samples = [x for x in json.loads((HERE / "samples.json").read_text(encoding="utf-8"))["samples"] if not x.get("holdout")]
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    return all(prog.get(x["id"], {}).get("status") in ("done", "not_converged", "failed") for x in samples)


def keepalive():
    """supervise.py(WSL 창구를 열어 둔 채 run_batch를 앞에서 돌린다)로 계산한다. 중간에 죽으면 다시 시작한다(최대 30번)."""
    for n in range(30):
        subprocess.run([sys.executable, str(HERE / "supervise.py"), "/mnt/d/Test/experiments/openfoam_baseline/surrogate/start_batch.sh",
                        "--spec", "/mnt/d/Test/experiments/openfoam_baseline/surrogate/samples.json"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
        if finished():
            return
        w(f"계산이 끝나지 않고 멈춤, 다시 시작 #{n + 1}")
        time.sleep(10)


w("1단계 시작")
keepalive()
w("1단계 끝")
prog = json.loads(PROG.read_text(encoding="utf-8"))
for sid in RERUN:
    if prog.get(sid, {}).get("status") == "not_converged":
        prog.pop(sid)
PROG.write_text(json.dumps(prog, indent=1, ensure_ascii=False), encoding="utf-8")
w("2단계 시작(미수렴 9개 재계산, 한도 5500회)")
keepalive()
w("2단계 끝")
