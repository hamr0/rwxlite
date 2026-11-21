#!/bin/bash
# Round 16 labelling, opinion 2: R13 (rwxlite 0.3.1 int8-pc) through rwxmap 1c25be1 mode a on the laptop, via r15/label_r13.mjs unchanged, 2 threads (as r15). Resumable.
# Needs data/r16/labels/work/{ops,mech}.jsonl (r16/label_prep.py, r15/label_mech.mjs). Start: nohup r16/label_r13.sh > data/r16/labels/work/r13.log 2>&1 &
cd "$(dirname "$0")/.." || exit 1
W=data/r16/labels/work
sha256sum data/m1-r13/model-int8-pc.onnx
exec nice -n 19 node r15/label_r13.mjs --tree "$PWD/data/r16/scratch/rwxmap-1c25be1" --ops $W/ops.jsonl --mech $W/mech.jsonl --model-dir data/m1-r13 --out $W/r13 --threads 2
