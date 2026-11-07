#!/bin/bash
# Round 13 on the home server. Usage: r13-train.sh R13 | R13-L3 | R13-L3-t2   (R13-L3-t2 = R13-L3 on the text-format-2 data data/round13-t2, prereg-r13.md section 4b).
# Each candidate runs in its own dir ~/rwxlite-train/r13-<name>/ (own copy of train/ and data/train/{train,val,v3eval}.parquet from data/round13, same data for all candidates).
# Recipe = round 12 S0 (= round 11), unchanged: base all-MiniLM-L6-v2 (no --init), --soft --alpha 0.7, 1 epoch, bs 32, lr 5e-5, max_len 128, x_weight 1.0, seed 1, --threads 4 --ckpt 250.
# R13-L3 adds ONLY --loose_cost 3 (train/losscost.py: loss = recipe loss + mean_i sum_j p_ij * cost(y_i, j), cost 3 below the hard label, 1 above, 0 at it).
# R13-L3-t2 = R13-L3 with data/round13-t2/{train,val,v3eval}.{jsonl,parquet} copied into its dir's data/train/ instead of data/round13 (same labels and targets, only text differs: format 2).
# Start (not before the prereg is committed and the user has confirmed):  nohup ~/rwxlite-train/r13-train.sh R13 > ~/rwxlite-train/r13-R13.log 2>&1 & echo $! > ~/rwxlite-train/r13-R13.pid
# Re-running resumes from last.pt. Nothing else under ~/rwxlite-train is touched. Run the candidates one after the other (4 CPU threads each).
export HF_HOME=$HOME/rwxlite-train/hf-cache
PY=$HOME/rwxlite-train/.venv/bin/python
case "$1" in
  R13)    EXTRA="";               TAG=r13 ;;
  R13-L3) EXTRA="--loose_cost 3"; TAG=r13-L3 ;;
  R13-L3-t2) EXTRA="--loose_cost 3"; TAG=r13-L3-t2 ;;
  *) echo "usage: $0 R13|R13-L3|R13-L3-t2"; exit 2 ;;
esac
D=$HOME/rwxlite-train/r13-$1; cd $D || exit 1
echo "$(date -Is) start $1"
$PY train/finetune.py --epochs 1 --soft --alpha 0.7 --threads 4 --ckpt 250 $EXTRA --tag $TAG > data/train/finetune-$TAG.log 2>&1
echo "$(date -Is) done $1 exit $?"
