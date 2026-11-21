#!/bin/bash
# r16 driver: while the search runs, repeatedly look up licences and fetch new candidates (all resumable).
cd "$(dirname "$0")/.." || exit 1
SP=$(cat data/r16/run/search.pid)
while true; do
  alive=0; kill -0 "$SP" 2>/dev/null && alive=1
  [ -s data/r16/raw/candidates.jsonl ] && { nice -n 19 python3 r16/licences.py; nice -n 19 python3 r16/fetch.py; }
  [ $alive = 0 ] && break
  sleep 120
done
echo "drive complete"
