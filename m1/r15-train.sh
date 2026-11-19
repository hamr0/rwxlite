#!/bin/bash
# Round 15 on the home server (docs/wiki/prereg-r15.md section 4/5). Usage: r15-train.sh teacher | probs | student | probs-fallback-check   (one phase at a time, never in parallel)
# Gentle rules: nice 19, ionice idle, 3 of 4 threads, one job, nohup, memwatch kills python if MemAvailable < 2 GB (lowest seen goes to memwatch-<phase>.log). Re-running resumes from last.pt.
#   teacher : stage A. bge-base-en-v1.5 on the 302,268 rows (R13 rows with R13 soft targets, r15 rows one-hot cascade labels, per-row weight), tag r15-teacher, dir ~/rwxlite-train/r15-teacher/
#   probs   : stage A to B. teacher softmax (T=1, fp32) over train.parquet -> data/train/teacher-r15-train.npy (train/teacher_probs.py, unchanged), same dir
#   student : stage B. all-MiniLM-L6-v2 with --teacher teacher-r15-train.npy, tag r15-student, dir ~/rwxlite-train/r15-student/ (own copy of train/ and data/train/{train,val,v3eval}.parquet + teacher-r15-train.npy and its .json)
# Start (on the server):  nohup ~/rwxlite-train/r15-train.sh teacher > ~/rwxlite-train/r15-teacher.log 2>&1 & echo $! > ~/rwxlite-train/r15-teacher.pid
export HF_HOME=$HOME/rwxlite-train/hf-cache OMP_NUM_THREADS=3
PY=$HOME/rwxlite-train/.venv/bin/python
case "$1" in
  teacher) D=$HOME/rwxlite-train/r15-teacher
           CMD="$PY train/finetune.py --base BAAI/bge-base-en-v1.5 --teacher data/train/targets-teacher.npy --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 5e-5 --max_len 128 --threads 3 --ckpt 250 --tag r15-teacher"
           LOG=data/train/finetune-r15-teacher.log ;;
  probs)   D=$HOME/rwxlite-train/r15-teacher
           CMD="$PY train/teacher_probs.py --ckpt data/train/ckpt-r15-teacher/final --out data/train/teacher-r15-train.npy --threads 3"
           LOG=data/train/teacher-probs-r15.log ;;
  student) D=$HOME/rwxlite-train/r15-student
           CMD="$PY train/finetune.py --teacher data/train/teacher-r15-train.npy --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 5e-5 --max_len 128 --threads 3 --ckpt 250 --tag r15-student"
           LOG=data/train/finetune-r15-student.log ;;
  *) echo "usage: $0 teacher|probs|student"; exit 2 ;;
esac
cd $D || exit 1
echo "$(date -Is) start $1"
# finetune.py / teacher_probs.py find data/train relative to the repo layout (common.OUT = <root>/data/train, root = parent of train/), so $D has train/ and data/train/ exactly as in rounds 13/14
nice -n 19 ionice -c3 $CMD > $LOG 2>&1 &
PID=$!; echo $PID > python-$1.pid
( min=99999999; while kill -0 $PID 2>/dev/null; do
    av=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); [ "$av" -lt "$min" ] && min=$av && echo "$(date -Is) lowest MemAvailable so far ${av} kB" > memwatch-$1.log
    if [ "$av" -lt 2097152 ]; then echo "$(date -Is) MemAvailable ${av} kB < 2 GB: killing python pid $PID" >> memwatch-$1.log; kill $PID; sleep 5; kill -9 $PID 2>/dev/null; break; fi
    sleep 60; done ) &
MW=$!; echo $MW > memwatch-$1.pid
wait $PID; rc=$?; echo "$(date -Is) done $1 exit $rc"; kill $MW 2>/dev/null; exit $rc
