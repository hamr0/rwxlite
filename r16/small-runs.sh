#!/bin/bash
# Round 16 small comparison runs on the home server (docs/product/prereg-r16-small-runs.md section 6). NOT run yet. Usage: small-runs.sh tA | tB | probsA | soften | sS0 | sS1   (one phase at a time, never in parallel)
# Gentle rules as m1/r15-train.sh: nice 19, ionice idle, 3 of 4 threads, one job, memwatch kills python if MemAvailable < 2 GB. Re-running resumes from last.pt. Own dirs only: ~/rwxlite-train/r16-small/<arm>/ (new, empty before setup).
#   tA   : teacher, set-A (30k new + 6k old), continue from the r15 bge teacher, lr 2e-5, hard-label weighted CE   dir tA
#   tB   : teacher, set-B (30k new + 30k old), same                                                               dir tB
#   probsA: r15 teacher softmax (T=1, fp32) over set-A (train/teacher_probs.py, unchanged)                           dir probsA
#   soften: softmax(log p / 1.362087) of probsA's file (r16/soften_probs.py)                                      dir probsA
#   sS0  : student from the r15 student, set-A, --teacher T=1 probs, alpha 0.7, lr 2e-5                            dir sS0
#   sS1  : same with the softened probs                                                                         dir sS1
export HF_HOME=$HOME/rwxlite-train/hf-cache OMP_NUM_THREADS=3
PY=$HOME/rwxlite-train/.venv/bin/python; B=$HOME/rwxlite-train/r16-small
T15=$HOME/rwxlite-train/r15-teacher/data/train/ckpt-r15-teacher/final; S15=$HOME/rwxlite-train/r15-student/data/train/ckpt-r15-student/final
COMMON="--row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250"
case "$1" in
  tA) D=$B/tA; CMD="$PY train/finetune.py --base BAAI/bge-base-en-v1.5 --init $T15 $COMMON --tag r16-tA"; LOG=data/train/finetune-r16-tA.log ;;
  tB) D=$B/tB; CMD="$PY train/finetune.py --base BAAI/bge-base-en-v1.5 --init $T15 $COMMON --tag r16-tB"; LOG=data/train/finetune-r16-tB.log ;;
  probsA) D=$B/probsA; CMD="$PY train/teacher_probs.py --ckpt $T15 --out data/train/teacher-r15-on-setA.npy --threads 3"; LOG=data/train/teacher-probs-setA.log ;;
  soften) D=$B/probsA; CMD="$PY r16/soften_probs.py --in data/train/teacher-r15-on-setA.npy --T 1.362087 --out data/train/teacher-r15-on-setA-soft1362087.npy"; LOG=data/train/soften.log ;;
  sS0) D=$B/sS0; CMD="$PY train/finetune.py --init $S15 --teacher data/train/teacher-r15-on-setA.npy $COMMON --tag r16-sS0"; LOG=data/train/finetune-r16-sS0.log ;;
  sS1) D=$B/sS1; CMD="$PY train/finetune.py --init $S15 --teacher data/train/teacher-r15-on-setA-soft1362087.npy $COMMON --tag r16-sS1"; LOG=data/train/finetune-r16-sS1.log ;;
  *) echo "usage: $0 tA|tB|probsA|soften|sS0|sS1"; exit 2 ;;
esac
cd $D || exit 1
echo "$(date -Is) start $1"
nice -n 19 ionice -c3 $CMD > $LOG 2>&1 &
PID=$!; echo $PID > python-$1.pid
( min=99999999; while kill -0 $PID 2>/dev/null; do
    av=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); [ "$av" -lt "$min" ] && min=$av && echo "$(date -Is) lowest MemAvailable so far ${av} kB" > memwatch-$1.log
    if [ "$av" -lt 2097152 ]; then echo "$(date -Is) MemAvailable ${av} kB < 2 GB: killing python pid $PID" >> memwatch-$1.log; kill $PID; sleep 5; kill -9 $PID 2>/dev/null; break; fi
    sleep 60; done ) &
MW=$!; echo $MW > memwatch-$1.pid
wait $PID; rc=$?; echo "$(date -Is) done $1 exit $rc"; kill $MW 2>/dev/null; exit $rc
