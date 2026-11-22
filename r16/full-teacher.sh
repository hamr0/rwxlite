#!/bin/bash
# Round 16 FULL teacher (docs/product/prereg-r16-small-runs.md section 14): continue from the r15 bge teacher on teacher-train-v3, tA recipe. Gentle rules as r16/small-runs.sh:
# nice 19, ionice idle, 3 of 4 threads, one job, memwatch kills python if MemAvailable < 2 GB. Re-running resumes from last.pt. Own dir only: ~/rwxlite-train/r16-full/teacher/
# Start on the server:  cd ~/rwxlite-train/r16-full/teacher && nohup ./full-teacher.sh > run.log 2>&1 & echo $! > run.pid
export HF_HOME=$HOME/rwxlite-train/hf-cache OMP_NUM_THREADS=3
PY=$HOME/rwxlite-train/.venv/bin/python; D=$HOME/rwxlite-train/r16-full/teacher
T15=$HOME/rwxlite-train/r15-teacher/data/train/ckpt-r15-teacher/final
CMD="$PY train/finetune.py --base BAAI/bge-base-en-v1.5 --init $T15 --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250 --tag r16-full-teacher"; LOG=data/train/finetune-r16-full-teacher.log
cd $D || exit 1
echo "$(date -Is) start full-teacher"
nice -n 19 ionice -c3 $CMD >> $LOG 2>&1 &
PID=$!; echo $PID > python-full-teacher.pid
( min=99999999; while kill -0 $PID 2>/dev/null; do
    av=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); [ "$av" -lt "$min" ] && min=$av && echo "$(date -Is) lowest MemAvailable so far ${av} kB" > memwatch-full-teacher.log
    if [ "$av" -lt 2097152 ]; then echo "$(date -Is) MemAvailable ${av} kB < 2 GB: killing python pid $PID" >> memwatch-full-teacher.log; kill $PID; sleep 5; kill -9 $PID 2>/dev/null; break; fi
    sleep 60; done ) &
MW=$!; echo $MW > memwatch-full-teacher.pid
wait $PID; rc=$?; echo "$(date -Is) done full-teacher exit $rc"; kill $MW 2>/dev/null; exit $rc
