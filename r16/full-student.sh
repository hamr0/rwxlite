#!/bin/bash
# Round 16 FULL student (docs/product/prereg-r16-small-runs.md section 16): phase 1 "probs" = the full r16 teacher's T=1 softmax over teacher-train-v3, phase 2 "student" = MiniLM from the r15 student (0.4.0), sS0 recipe. Phase 2 starts only if phase 1 exited 0.
# Gentle rules as r16/small-runs.sh: nice 19, ionice idle, 3 of 4 threads, one job, nohup, logs appended, memwatch kills python if MemAvailable < 2 GB. Re-running skips a finished phase (marker done-<phase>) and a half-done training resumes from last.pt.
# Own dir only: ~/rwxlite-train/r16-full/student/. The teacher checkpoint (r16-full/teacher/...) is read only, referenced not copied.
# Start on the server:  cd ~/rwxlite-train/r16-full/student && nohup ./full-student.sh > run.log 2>&1 & echo $! > run.pid
export HF_HOME=$HOME/rwxlite-train/hf-cache OMP_NUM_THREADS=3
PY=$HOME/rwxlite-train/.venv/bin/python; D=$HOME/rwxlite-train/r16-full/student
TEACH=$HOME/rwxlite-train/r16-full/teacher/data/train/ckpt-r16-full-teacher/final; S15=$HOME/rwxlite-train/r15-student/data/train/ckpt-r15-student/final
PROBS=data/train/teacher-r16-full-on-v3.npy
CMD_probs="$PY train/teacher_probs.py --ckpt $TEACH --out $PROBS --threads 3"; LOG_probs=data/train/teacher-probs-r16-full-on-v3.log
CMD_student="$PY train/finetune.py --init $S15 --teacher $PROBS --row_weight weight --alpha 0.7 --epochs 1 --bs 32 --lr 2e-5 --max_len 128 --threads 3 --ckpt 250 --tag r16-full-student"; LOG_student=data/train/finetune-r16-full-student.log
cd $D || exit 1
phase() {  # $1 = probs | student
  local ph=$1 cmd log
  [ -f done-$ph ] && { echo "$(date -Is) skip $ph (done)"; return 0; }
  eval cmd=\$CMD_$ph; eval log=\$LOG_$ph
  echo "$(date -Is) start $ph"
  nice -n 19 ionice -c3 $cmd >> $log 2>&1 &
  local PID=$!; echo $PID > python-$ph.pid
  ( min=99999999; while kill -0 $PID 2>/dev/null; do
      av=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); [ "$av" -lt "$min" ] && min=$av && echo "$(date -Is) lowest MemAvailable so far ${av} kB" > memwatch-$ph.log
      if [ "$av" -lt 2097152 ]; then echo "$(date -Is) MemAvailable ${av} kB < 2 GB: killing python pid $PID" >> memwatch-$ph.log; kill $PID; sleep 5; kill -9 $PID 2>/dev/null; break; fi
      sleep 60; done ) &
  local MW=$!; echo $MW > memwatch-$ph.pid
  wait $PID; local rc=$?; echo "$(date -Is) done $ph exit $rc"; kill $MW 2>/dev/null
  [ $rc -eq 0 ] && touch done-$ph
  return $rc
}
phase probs || { echo "$(date -Is) CHAIN STOP: probs failed"; exit 1; }
[ -s $PROBS ] && [ -s $PROBS.json ] || { echo "$(date -Is) CHAIN STOP: $PROBS missing after probs"; exit 1; }
phase student || { echo "$(date -Is) CHAIN STOP: student failed"; exit 1; }
echo "$(date -Is) CHAIN DONE"
