#!/bin/bash
# Round 16 rating: r15 bge teacher over the new-pick + dev texts on the home server. Own dir ~/rwxlite-train/r16-rate/ (v2 re-rating of the added rows: RATE_DIR=r16-rate-v2) (nothing else touched).
# nice 19, ionice idle, 3 threads, one job; memwatch kills python if MemAvailable < 2 GB. Reuses r15/label_bge.py unchanged (raw logits, resumable chunks).
# Start: nohup ~/rwxlite-train/r16-rate/rate_bge.sh > ~/rwxlite-train/r16-rate/run.log 2>&1 & echo $! > ~/rwxlite-train/r16-rate/run.pid
export HF_HOME=$HOME/rwxlite-train/hf-cache OMP_NUM_THREADS=3
D=$HOME/rwxlite-train/${RATE_DIR:-r16-rate}; cd $D || exit 1
PY=$HOME/rwxlite-train/.venv/bin/python
CK=$HOME/rwxlite-train/r15-teacher/data/train/ckpt-r15-teacher/final
echo "$(date -Is) start ckpt sha256 $(sha256sum $CK/model.safetensors | cut -d' ' -f1)"
nice -n 19 ionice -c3 $PY label_bge.py --ckpt $CK --texts texts.jsonl --out chunks --chunk 4000 --bs 64 --threads 3 &
PID=$!; echo $PID > python.pid
( min=99999999; while kill -0 $PID 2>/dev/null; do
    av=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); [ "$av" -lt "$min" ] && min=$av && echo "$(date -Is) lowest MemAvailable so far ${av} kB" > memwatch.log
    if [ "$av" -lt 2097152 ]; then echo "$(date -Is) MemAvailable ${av} kB < 2 GB: killing python pid $PID" >> memwatch.log; kill $PID; sleep 5; kill -9 $PID 2>/dev/null; break; fi
    sleep 60; done ) &
MW=$!; echo $MW > memwatch.pid
wait $PID; rc=$?; echo "$(date -Is) python exit $rc"; kill $MW 2>/dev/null; exit $rc
