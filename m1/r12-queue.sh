#!/bin/bash
# Sequential queue for round 12 (S0, S1, S2) on the home server. Each run in ~/rwxlite-train/r12-<X>/ (own copy of train/ = the r11 scripts, and data/train/{train,val,v3eval}.parquet).
# Recipe = round 11's, unchanged: base all-MiniLM-L6-v2 (no --init), --soft --alpha 0.7, 1 epoch, bs 32, lr 5e-5, max_len 128, x_weight 1.0, seed 1, --threads 4 --ckpt 250.
# Start: nohup ~/rwxlite-train/r12-queue.sh > ~/rwxlite-train/r12-queue.log 2>&1 & echo $! > ~/rwxlite-train/r12.pid
# A run that fails does not stop the next one; exit codes are in the queue log. Re-running resumes from last.pt.
export HF_HOME=$HOME/rwxlite-train/hf-cache
PY=$HOME/rwxlite-train/.venv/bin/python
for X in S0 S1 S2; do
  D=$HOME/rwxlite-train/r12-$X; cd $D || exit 1
  echo "$(date -Is) start $X"
  $PY train/finetune.py --epochs 1 --soft --alpha 0.7 --threads 4 --ckpt 250 --tag r12-$X > data/train/finetune-r12-$X.log 2>&1
  echo "$(date -Is) done $X exit $?"
done
echo "$(date -Is) queue finished"
