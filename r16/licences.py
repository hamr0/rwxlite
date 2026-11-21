#!/usr/bin/env python3
"""r16 (copy of r15, paths changed) step 2: repo metadata (licence, fork/parent, archived, stars, pushed_at) via GraphQL.

Reads unique repos from data/r16/raw/candidates.jsonl, queries 40 repos per GraphQL call,
appends to data/r16/raw/repos.jsonl (all repos, with `kept` = spdx in the permissive set).
Resumable: repos already in repos.jsonl are skipped; run again after search has grown.
    nice -n 19 python3 r16/licences.py
Quarantined: metadata only, no labelling.
"""
import json, os, subprocess, sys, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "r16", "raw"))
CAND, REPOS = os.path.join(ROOT, "candidates.jsonl"), os.path.join(ROOT, "repos.jsonl")
OK = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "ISC", "Unlicense"}
BATCH = 40
FIELDS = "nameWithOwner licenseInfo{spdxId} isFork parent{nameWithOwner} isArchived stargazerCount pushedAt"


def gql(repos):
    parts = []
    for i, r in enumerate(repos):
        o, n = r.split("/", 1)
        parts.append('r%d: repository(owner:%s, name:%s){%s}' % (i, json.dumps(o), json.dumps(n), FIELDS))
    q = "{" + " ".join(parts) + "}"
    delay = 20
    while True:
        p = subprocess.run(["gh", "api", "graphql", "-f", "query=" + q], capture_output=True, text=True)
        try:
            d = json.loads(p.stdout)
        except Exception:
            d = None
        if d and "data" in d and d["data"] is not None:
            return d["data"]
        msg = (p.stdout + p.stderr)[:300]
        print("graphql problem:", msg, flush=True)
        if "rate limit" in msg.lower():
            delay = 600
        time.sleep(delay); delay = min(delay * 2, 900)


def main():
    seen = set()
    if os.path.exists(REPOS):
        for l in open(REPOS):
            if l.strip():
                seen.add(json.loads(l)["repo"])
    todo = []
    s2 = set()
    for l in open(CAND):
        if not l.strip():
            continue
        r = json.loads(l)["repo"]
        if r not in seen and r not in s2:
            s2.add(r); todo.append(r)
    print("repos to look up:", len(todo), flush=True)
    with open(REPOS, "a") as out:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            data = gql(chunk)
            for j, r in enumerate(chunk):
                v = data.get("r%d" % j)
                if v is None:  # deleted/renamed/inaccessible
                    rec = {"repo": r, "missing": True, "kept": False}
                else:
                    spdx = (v.get("licenseInfo") or {}).get("spdxId")
                    rec = {"repo": r, "full_name": v["nameWithOwner"], "spdx": spdx, "is_fork": v["isFork"],
                           "fork_parent": (v.get("parent") or {}).get("nameWithOwner"),
                           "archived": v["isArchived"], "stars": v["stargazerCount"], "pushed_at": v["pushedAt"],
                           "kept": spdx in OK}
                out.write(json.dumps(rec) + "\n")
            out.flush()
            if (i // BATCH) % 25 == 0:
                print("done", i + len(chunk), "/", len(todo), flush=True)
    print("licences complete", flush=True)


if __name__ == "__main__":
    main()
