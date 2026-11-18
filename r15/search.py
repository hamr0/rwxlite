#!/usr/bin/env python3
"""r15 step 1: GitHub code search for OpenAPI/Swagger spec files.  QUARANTINED: no labelling.

Each query (filename + content marker) is sharded by the `size:` qualifier; a shard
whose total_count is > 1000 is split in two until it fits (code search returns at most
1000 results per query).  Rate limit: 10 requests/min, so ~6.5 s between calls, with
back-off on 403/429.

Run (resumable; re-run the same command after any stop):
    nice -n 19 nohup python3 r15/search.py > data/r15/raw/search.log 2>&1 &
Optional: --only openapi.yaml   (restrict to one query), --max-calls N.
Output : data/r15/raw/candidates.jsonl  (repo, path, sha, html_url, size_shard, query)
Progress: data/r15/raw/search_shards.jsonl (one line per finished/split shard).
Note: the code-search API does not return file size; size_shard is the size: range
that found the file.  Exact size is recorded later by fetch.py.
"""
import argparse, json, math, subprocess, sys, time, os, re
from urllib.parse import quote

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "r15", "raw")
RAW = os.path.normpath(RAW)
CAND = os.path.join(RAW, "candidates.jsonl")
SHARDS = os.path.join(RAW, "search_shards.jsonl")
SLEEP = 6.5
MIN_SIZE, MAX_SIZE = 3000, 400000  # <3 KB rarely holds 5 real operations; code search skips >384 KB

QUERIES = [  # (id, qualifier+marker string)
    ("openapi.yaml", 'filename:openapi.yaml "openapi: 3"'),
    ("swagger.yaml", 'filename:swagger.yaml "swagger: \\"2.0\\""'),
    ("openapi.json", 'filename:openapi.json "openapi"'),
    ("swagger.json", 'filename:swagger.json "swagger"'),
    ("openapi.yml", 'filename:openapi.yml "openapi: 3"'),
    ("swagger.yml", 'filename:swagger.yml "swagger: \\"2.0\\""'),
]

calls = 0
max_calls = None


def gh_search(q, page):
    """One code-search call; returns (json, ok). Handles rate limits."""
    global calls
    backoff = 30
    while True:
        if max_calls is not None and calls >= max_calls:
            print("max-calls reached", flush=True); sys.exit(0)
        time.sleep(SLEEP)
        calls += 1
        p = subprocess.run(["gh", "api", "-i", "-X", "GET", "search/code", "-f", "q=" + q,
                            "-f", "per_page=100", "-f", "page=%d" % page],
                           capture_output=True, text=True)
        head, _, body = p.stdout.partition("\n\n")
        m = re.match(r"HTTP/\S+ (\d+)", head)
        status = int(m.group(1)) if m else 0
        if status == 200:
            return json.loads(body), True
        hdr = {l.split(":", 1)[0].lower(): l.split(":", 1)[1].strip() for l in head.splitlines()[1:] if ":" in l}
        print("status", status, body[:200].replace("\n", " "), flush=True)
        if status in (403, 429):
            wait = backoff
            if "retry-after" in hdr:
                wait = max(wait, int(hdr["retry-after"]) + 5)
            elif hdr.get("x-ratelimit-remaining") == "0" and "x-ratelimit-reset" in hdr:
                wait = max(wait, int(hdr["x-ratelimit-reset"]) - int(time.time()) + 5)
            print("rate-limited, sleeping", wait, flush=True)
            time.sleep(wait); backoff = min(backoff * 2, 900)
        elif status == 0 or status >= 500:
            time.sleep(backoff); backoff = min(backoff * 2, 900)
        else:
            return None, False  # 422 etc.


def load_shards():
    d = {}
    if os.path.exists(SHARDS):
        for line in open(SHARDS):
            if line.strip():
                r = json.loads(line); d[(r["q"], r["lo"], r["hi"])] = r
    return d


def process(qid, qtext, lo, hi, shards, out, sf):
    key = (qid, lo, hi)
    if key in shards:
        r = shards[key]
        if r["status"] == "split":
            for a, b in r["children"]:
                process(qid, qtext, a, b, shards, out, sf)
        return
    q = "%s size:%d..%d" % (qtext, lo, hi)
    data, ok = gh_search(q, 1)
    if not ok:
        rec = {"q": qid, "lo": lo, "hi": hi, "status": "error"}
        sf.write(json.dumps(rec) + "\n"); sf.flush(); return
    total = data.get("total_count", 0)
    if total > 1000 and hi > lo:
        mid = int(math.sqrt(lo * hi)) if hi / max(lo, 1) > 2 else (lo + hi) // 2
        mid = min(max(mid, lo), hi - 1)
        ch = [(lo, mid), (mid + 1, hi)]
        rec = {"q": qid, "lo": lo, "hi": hi, "status": "split", "total": total, "children": ch}
        sf.write(json.dumps(rec) + "\n"); sf.flush(); shards[key] = rec
        for a, b in ch:
            process(qid, qtext, a, b, shards, out, sf)
        return
    pages = min(10, math.ceil(total / 100))
    n = 0
    for pg in range(1, pages + 1):
        if pg > 1:
            data, ok = gh_search(q, pg)
            if not ok:
                break
        for it in data.get("items", []):
            out.write(json.dumps({"repo": it["repository"]["full_name"], "path": it["path"], "sha": it["sha"],
                                  "html_url": it["html_url"], "size_shard": [lo, hi], "query": qid}) + "\n")
            n += 1
        out.flush()
    rec = {"q": qid, "lo": lo, "hi": hi, "status": "done", "total": total, "got": n,
           "overflow": total > 1000}
    sf.write(json.dumps(rec) + "\n"); sf.flush(); shards[key] = rec
    print("done %s %d..%d total=%d got=%d calls=%d" % (qid, lo, hi, total, n, calls), flush=True)


def main():
    global max_calls
    ap = argparse.ArgumentParser()
    ap.add_argument("--only"); ap.add_argument("--max-calls", type=int)
    a = ap.parse_args(); max_calls = a.max_calls
    os.makedirs(RAW, exist_ok=True)
    shards = load_shards()
    with open(CAND, "a") as out, open(SHARDS, "a") as sf:
        for qid, qtext in QUERIES:
            if a.only and a.only != qid:
                continue
            process(qid, qtext, MIN_SIZE, MAX_SIZE, shards, out, sf)
    print("search complete", flush=True)


if __name__ == "__main__":
    main()
