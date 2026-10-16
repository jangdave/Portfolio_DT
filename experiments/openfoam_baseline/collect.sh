#!/bin/bash
# 사례가 끝나는 대로 결과 CSV를 results/에 저장한다. 사용: collect.sh <사례 폴더 이름>... (이름 끝의 _dx10은 파일 이름에서 뺀다)
export WM_PROJECT_DIR=/usr/share/openfoam
R=/mnt/d/Test/experiments/openfoam_baseline
for n in "$@"; do
  while [ ! -f ~/foam_runs/$n/timing.txt ]; do sleep 15; done
  python3 $R/extract.py ~/foam_runs/$n $R/results/rack_inlet_${n%_dx10} > ~/foam_runs/$n/extract.out 2>&1
  { cat ~/foam_runs/$n/timing.txt; grep -c '^Time =' ~/foam_runs/$n/log.solver; grep converged ~/foam_runs/$n/log.solver; grep cells: ~/foam_runs/$n/log.checkMesh; } > $R/results/run_${n%_dx10}.txt 2>&1
done
