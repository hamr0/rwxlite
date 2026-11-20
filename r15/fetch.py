#!/usr/bin/env python3
"""r15 step 3: download kept spec files (licence-kept repos only) from raw.githubusercontent.com
at the sha found by search (blob sha -> we use the commit-independent URL from html_url, i.e. the
commit sha embedded in html_url).  Concurrency <= 4, retries with back-off.

Output: data/r15/raw/specs/<sha256-of-url-key>.{json,yaml}  (name = hash of repo+path+commit)
        data/r15/raw/fetched.jsonl  one line per file: repo, path, commit, file (rel), size, content_sha256, status
Resumable: entries already in fetched.jsonl are skipped.  Identical content is stored once per
content hash would hide provenance, so every file is kept; exact-content dedupe happens in filter.py.
    nice -n 19 python3 r15/fetch.py
Quarantined: download only.
"""
import hashlib, json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "r15", "raw"))
CAND, REPOS = os.path.join(ROOT, "candidates.jsonl"), os.path.join(ROOT, "repos.jsonl")
OUT, SPECS = os.path.join(ROOT, "fetched.jsonl"), os.path.join(ROOT, "specs")
MAXBYTES = 8_000_000


def key(repo, path, commit):
    return hashlib.sha256(("%s\0%s\0%s" % (repo, path, commit)).encode()).hexdigest()[:24]


def commit_of(html_url):
    m = re.search(r"/blob/([0-9a-f]{40})/", html_url)
    return m.group(1) if m else None


def get(url):
    delay = 2
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rwxlite-r15-collector"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(MAXBYTES + 1)
                return 200, data
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 451):
                return e.code, b""
            time.sleep(delay * (5 if e.code == 429 else 1)); delay *= 2
        except Exception:
            time.sleep(delay); delay *= 2
    return 0, b""


def work(c):
    repo, path, commit = c["repo"], c["path"], c["commit"]
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (repo, commit, urllib.parse.quote(path))
    st, data = get(url)
    rec = {"repo": repo, "path": path, "commit": commit, "status": st}
    if st == 200:
        if len(data) > MAXBYTES:
            rec["status"] = "toobig"; return rec
        ext = "json" if path.lower().endswith(".json") else "yaml"
        fn = "%s.%s" % (key(repo, path, commit), ext)
        with open(os.path.join(SPECS, fn), "wb") as f:
            f.write(data)
        rec.update(file=fn, size=len(data), content_sha256=hashlib.sha256(data).hexdigest())
    return rec


def main():
    os.makedirs(SPECS, exist_ok=True)
    kept = set()
    for l in open(REPOS):
        if l.strip():
            r = json.loads(l)
            if r.get("kept"):
                kept.add(r["repo"])
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            if l.strip():
                r = json.loads(l); done.add((r["repo"], r["path"], r["commit"]))
    todo, seen = [], set()
    for l in open(CAND):
        if not l.strip():
            continue
        c = json.loads(l)
        if c["repo"] not in kept:
            continue
        c["commit"] = commit_of(c["html_url"])
        if not c["commit"]:
            continue
        k = (c["repo"], c["path"], c["commit"])
        if k in done or k in seen:
            continue
        seen.add(k); todo.append(c)
    print("to fetch:", len(todo), flush=True)
    n = 0
    with open(OUT, "a") as out, ThreadPoolExecutor(4) as ex:
        for rec in ex.map(work, todo):
            out.write(json.dumps(rec) + "\n"); n += 1
            if n % 500 == 0:
                out.flush(); print("fetched", n, "/", len(todo), flush=True)
    print("fetch complete", flush=True)


if __name__ == "__main__":
    main()
