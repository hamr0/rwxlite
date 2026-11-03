#!/bin/sh
# Pass 1 then re-ask, resumable. Run from the repo root: nohup sh m0/run-step2.sh &
cd "$(dirname "$0")/.." || exit 1
node m0/jev-label.mjs >> data/m0/jev-pass1.log 2>&1 && node m0/jev-label.mjs --reask >> data/m0/jev-pass1.log 2>&1
