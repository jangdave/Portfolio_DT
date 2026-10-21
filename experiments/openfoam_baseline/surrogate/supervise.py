"""WSL 계산을 Windows 쪽에서 계속 붙들고 있는 감독 프로그램(WSL2 가상 머신이 유휴로 내려가 계산이 죽는 것을 막는다).
사용: python supervise.py <WSL에서 실행할 스크립트 경로> [인자...]   로그: supervise.log
wsl.exe를 stdin 파이프를 열어 둔 채 실행하고 끝날 때까지 기다린다. 끝나면 종료 코드와 시각을 로그에 적는다."""
import subprocess, sys, time
from pathlib import Path
log = Path(__file__).resolve().parent / "supervise.log"
def w(msg):
    with open(log, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
w("start " + " ".join(sys.argv[1:]))
p = subprocess.Popen(["wsl.exe", "-e", "bash"] + sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w(f"wsl pid {p.pid}")
rc = p.wait()
w(f"wsl exited rc={rc}")
