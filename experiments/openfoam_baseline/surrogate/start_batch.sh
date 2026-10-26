#!/bin/bash
# run_batch.py를 WSL 홈에서 실행하고 로그를 ~/surrogate_batch.log에 남긴다. 인자는 그대로 run_batch.py에 넘긴다.
cd ~
exec python3 /mnt/d/Test/experiments/openfoam_baseline/surrogate/run_batch.py "$@" >> ~/surrogate_batch.log 2>&1
