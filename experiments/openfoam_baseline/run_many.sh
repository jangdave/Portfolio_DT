#!/bin/bash
for n in "$@"; do bash /mnt/d/Test/experiments/openfoam_baseline/run_case.sh $n 16; done
