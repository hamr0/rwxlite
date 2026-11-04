#!/bin/bash
# Sequential queue for the held-out-vendor experiment (docs/wiki/holdout-r11.md), on the home server: A, then B, then C. Each run in ~/rwxlite-train/r11h-<X>/ (own copy of train/ and data/train/*.parquet).
# Start: nohup ~/rwxlite-train/r11h-queue.sh > ~/rwxlite-train/r11h-queue.log 2>&1 & echo $! > ~/rwxlite-train/r11h.pid
# A run that fails does not stop the next one; exit codes are in the queue log. Re-running resumes from last.pt.
export HF_HOME=$HOME/rwxlite-train/hf-cache
PY=$HOME/rwxlite-train/.venv/bin/python
for X in A B C; do
  D=$HOME/rwxlite-train/r11h-$X; cd $D || exit 1
  EXTRA=""; [ "$X" = C ] && EXTRA="--init $D/init-r8soft --lr 2.5e-5"
  echo "$(date -Is) start $X"
  $PY train/finetune.py --epochs 1 --soft --alpha 0.7 --threads 4 --ckpt 250 --tag r11h-$X $EXTRA > data/train/finetune-r11h-$X.log 2>&1
  echo "$(date -Is) done $X exit $?"
done
echo "$(date -Is) queue finished"
