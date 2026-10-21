"""WSL2는 유휴 상태가 1분쯤 이어지면 가상 머신을 내려서 백그라운드 계산도 같이 죽는다(이 PC에서 확인).
이 감독 프로그램은 Windows 쪽에서 계속 살아 있으면서 20초마다 짧은 wsl 명령을 보내 가상 머신을 깨워 두고,
run_batch.py가 없어졌는데 아직 끝나지 않았으면 다시 시작한다(run_batch.py는 끝난 샘플을 건너뛰고 이어서 한다).
사용 (Windows, 분리 실행): python keepalive.py [--spec 경로] — 로그 keepalive.log
종료: 모든 샘플이 done/not_converged/failed 가 되면 자동 종료. 수동 종료는 이 파이썬 프로세스를 끄고 WSL에서 `pkill -f run_batch.py`.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "keepalive.log"
PROG = HERE.parent / "results" / "surrogate" / "progress.json"
spec = sys.argv[sys.argv.index("--spec") + 1] if "--spec" in sys.argv else str(HERE / "samples.json")
wsl_spec = "/mnt/" + spec[0].lower() + spec[2:].replace("\\", "/") if ":" in spec else spec


def w(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def wsl(cmd, timeout=60):
    try:
        # CREATE_NO_WINDOW: 콘솔이 없는 분리 프로세스에서 wsl.exe를 부르면 매번 cmd 창이 깜빡이는 것을 막는다
        r = subprocess.run(["wsl.exe", "-e", "bash", "-c", cmd], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
        return r.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def finished() -> bool:
    samples = [s for s in json.loads(Path(spec).read_text(encoding="utf-8"))["samples"] if not s.get("holdout")]
    try:
        prog = json.loads(PROG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    return all(prog.get(s["id"], {}).get("status") in ("done", "not_converged", "failed") for s in samples)


def start():
    out = wsl(f"cd ~ && setsid nohup bash /mnt/d/Test/experiments/openfoam_baseline/surrogate/start_batch.sh --spec {wsl_spec} > /dev/null 2>&1 < /dev/null & sleep 2; echo started")
    w("start batch: " + out)


w(f"keepalive start spec={spec}")
# 이미 계산이 돌고 있으면(감독 프로그램만 바꿔 끼울 때) 두 번째 계산을 시작하지 않는다
if wsl("pgrep -f '[r]un_batch.py' > /dev/null && echo up || echo down") != "up":
    start()
else:
    w("batch already running; not starting another")
restarts = 0
while True:
    time.sleep(20)
    if finished():
        w("all samples finished; exit")
        break
    alive = wsl("pgrep -f '[r]un_batch.py' > /dev/null && echo up || echo down")
    if alive != "up":
        restarts += 1
        w(f"batch not running ({alive!r}); restart #{restarts}")
        if restarts > 30:
            w("too many restarts; give up")
            break
        start()
