#!/bin/bash
# 위에서 수렴한 1차 풍상(upwind) 결과에서 시작해 2차 풍상(linearUpwind)으로 이어서 계산한다(B 시나리오는 처음부터 시작하면 발산해서 이 방법을 썼다).
export WM_PROJECT_DIR=/usr/share/openfoam
SRC=$HOME/foam_runs/crac02_06_off_dx10; RUN=$HOME/foam_runs/crac02_06_off_dx10_lu
T=$(ls $SRC | grep -E '^[0-9]+$' | sort -n | tail -1)
cd $RUN; rm -rf processor* [1-9]*
cp -r $SRC/$T $RUN/$T
sed -i "s/endTime .*/endTime $((T+2500));/; s/writeInterval .*/writeInterval 2500;/" system/controlDict
T0=$(date +%s)
decomposePar -force -latestTime > log.decomposePar2 2>&1
mpirun --allow-run-as-root --oversubscribe -np 16 buoyantBoussinesqSimpleFoam -parallel > log.solver 2>&1 || true
T2=$(date +%s)
reconstructPar -latestTime > log.reconstructPar2 2>&1
echo "restart_from=$T solve_s=$((T2-T0)) cores=16" | tee timing.txt
