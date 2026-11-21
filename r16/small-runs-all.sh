#!/bin/bash
# Round 16 small runs, whole chain (docs/product/prereg-r16-small-runs.md section 6): tA -> tB -> probsA -> soften -> sS0 -> sS1.
# Each phase runs via small-runs.sh (nice 19, ionice idle, 3 threads, memwatch) and starts only after the previous one exited 0; a non-zero exit stops the chain.
# Start on the server:  cd ~/rwxlite-train/r16-small && nohup ./small-runs-all.sh > chain.log 2>&1 & echo $! > chain.pid
# Re-running skips phases that already finished (marker file done-<phase>), and a half-done training phase resumes from last.pt.
B=$HOME/rwxlite-train/r16-small
cd $B || exit 1
for ph in tA tB probsA soften sS0 sS1; do
  if [ -f $B/done-$ph ]; then echo "$(date -Is) skip $ph (done)"; continue; fi
  # the student arms read their teacher targets from their own data/train (set-A rows, order unchanged)
  if [ $ph = sS0 ]; then cp $B/probsA/data/train/teacher-r15-on-setA.npy $B/probsA/data/train/teacher-r15-on-setA.npy.json $B/sS0/data/train/ || { echo "$(date -Is) CHAIN STOP: copy for sS0 failed"; exit 1; }; fi
  if [ $ph = sS1 ]; then cp $B/probsA/data/train/teacher-r15-on-setA-soft1362087.npy $B/probsA/data/train/teacher-r15-on-setA-soft1362087.npy.json $B/sS1/data/train/ || { echo "$(date -Is) CHAIN STOP: copy for sS1 failed"; exit 1; }; fi
  $B/small-runs.sh $ph; rc=$?
  if [ $rc -ne 0 ]; then echo "$(date -Is) CHAIN STOP: phase $ph exit $rc"; exit $rc; fi
  touch $B/done-$ph
done
echo "$(date -Is) CHAIN DONE"
