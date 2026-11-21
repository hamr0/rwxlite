#!/usr/bin/env python3
"""r16 (copy of r15, paths changed) step 4: parse fetched specs and extract one row per operation.  QUARANTINED: no labelling.

Reads data/r16/raw/fetched.jsonl + repos.jsonl, parses each spec (YAML/JSON; invalid skipped),
keeps OpenAPI 3.x and Swagger 2.0, writes data/r16/raw/ops-raw.parquet and extract-stats.json.
Raw strings (summary/description) are stored untruncated and never printed.
vendor_key = registrable domain of servers/host; else of contact url/email; else normalised
info.title; else repo owner.  All alternative identity fields are kept (alias exclusion).
    nice -n 19 python3 r16/extract.py          (re-runs from scratch; takes minutes)
"""
import hashlib, json, os, re, sys
from multiprocessing import Pool
import yaml
import pyarrow as pa, pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "r16", "raw"))
METHODS = ["get", "put", "post", "delete", "patch", "head", "options", "trace", "query"]
Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

COLS = ["op_id", "method", "path", "operationId", "summary", "description", "spec_title", "spec_version_field",
        "servers", "x_logo", "contact_url", "contact_email", "contact_domain", "servers_domains", "logo_domain",
        "repo", "repo_owner", "repo_name", "file_path", "licence", "is_fork", "fork_parent", "stars", "pushed_at",
        "spec_sha256", "vendor_key", "vendor_key_source", "title_norm"]


def s(x):
    return x if isinstance(x, str) else ("" if x is None else str(x))


def server_urls(d):
    urls = []
    if "openapi" in d:
        for sv in (d.get("servers") or []):
            if not isinstance(sv, dict):
                continue
            u = s(sv.get("url"))
            for k, v in (sv.get("variables") or {}).items():
                if isinstance(v, dict):
                    u = u.replace("{%s}" % k, s(v.get("default")))
            urls.append(u)
    else:
        host = s(d.get("host"))
        if host:
            urls.append("%s%s" % (host, s(d.get("basePath"))))
        elif d.get("basePath"):
            urls.append(s(d.get("basePath")))
    return urls


def one(args):
    meta, = args
    try:
        raw = open(os.path.join(ROOT, "specs", meta["file"]), "rb").read()
        txt = raw.decode("utf-8", "replace")
        if meta["file"].endswith(".json"):
            d = json.loads(txt)
        else:
            d = yaml.load(txt, Loader=Loader)
    except Exception:
        return "invalid", []
    if not isinstance(d, dict):
        return "invalid", []
    ver = s(d.get("openapi")) if "openapi" in d else s(d.get("swagger"))
    if "openapi" in d:
        if not ver.startswith("3"):
            return "other-version", []
    elif "swagger" in d:
        if not ver.startswith("2"):
            return "other-version", []
    else:
        return "not-spec", []
    paths = d.get("paths")
    if not isinstance(paths, dict):
        return "no-paths", []
    info = d.get("info") if isinstance(d.get("info"), dict) else {}
    title = s(info.get("title"))
    contact = info.get("contact") if isinstance(info.get("contact"), dict) else {}
    logo = info.get("x-logo") if isinstance(info.get("x-logo"), dict) else {}
    logo_url = s(logo.get("url"))
    servers = server_urls(d)
    sdoms = sorted({x for x in (ids.domain(u) for u in servers) if x and not ids.is_generic_domain(x)})
    cdom_set = []
    for u in (contact.get("url"), contact.get("email"), info.get("termsOfService")):
        x = ids.domain(s(u)) if u else None
        if x and not ids.is_generic_domain(x):
            cdom_set.append(x)
    cdoms = sorted(set(cdom_set))
    ldom = ids.domain(logo_url) if logo_url else None
    ldom = ldom if ldom and not ids.is_generic_domain(ldom) else ""
    tn = ids.norm_title(title)
    owner = meta["repo"].split("/")[0]
    if sdoms:
        vk, src = sdoms[0], "server"
    elif cdoms:
        vk, src = cdoms[0], "contact"
    elif tn and tn not in ids.GENERIC_TITLES and len(tn) >= 3:
        vk, src = "title:" + tn, "title"
    else:
        vk, src = "owner:" + ids.norm(owner), "owner"
    rows = []
    for p, item in paths.items():
        if not isinstance(item, dict) or not isinstance(p, str) or not p.startswith("/"):
            continue
        for m in METHODS:
            op = item.get(m) if m in item else item.get(m.upper())
            if not isinstance(op, dict):
                continue
            h = hashlib.sha256(("%s\0%s\0%s\0%s\0%s" % (meta["repo"], meta["path"], meta["commit"], m, p)).encode()).hexdigest()[:16]
            rows.append([
                "r16-" + h, m.upper(), p, s(op.get("operationId")), s(op.get("summary")), s(op.get("description")),
                title, ver, "|".join(servers), logo_url, s(contact.get("url")), s(contact.get("email")),
                "|".join(cdoms), "|".join(sdoms), ldom, meta["repo"], owner, meta["repo"].split("/", 1)[1],
                meta["path"], (meta["spdx"] or "none"), bool(meta["is_fork"]), s(meta["fork_parent"]), int(meta["stars"] or 0),
                s(meta["pushed_at"]), meta["content_sha256"], vk, src, tn])
    return "ok", rows


def main():
    repos = {}
    for l in open(os.path.join(ROOT, "repos.jsonl")):
        if l.strip():
            r = json.loads(l)
            if not r.get("kept") and not r.get("missing") and not r.get("is_fork"):
                repos[r["repo"]] = r
    metas = []
    for l in open(os.path.join(ROOT, "fetched.jsonl")):
        if not l.strip():
            continue
        f = json.loads(l)
        if f.get("status") != 200 or f["repo"] not in repos:
            continue
        r = repos[f["repo"]]
        f.update(spdx=r["spdx"], is_fork=r["is_fork"], fork_parent=r["fork_parent"], stars=r["stars"], pushed_at=r["pushed_at"])
        metas.append((f,))
    schema = pa.schema([(c, pa.bool_() if c == "is_fork" else pa.int64() if c == "stars" else pa.string()) for c in COLS])
    stats = {}
    nrows = 0
    out = os.path.join(ROOT, "ops-raw.parquet")
    with pq.ParquetWriter(out, schema) as w, Pool(4) as pool:
        buf = []
        for st, rows in pool.imap(one, metas, chunksize=8):
            stats[st] = stats.get(st, 0) + 1
            buf.extend(rows)
            if len(buf) > 20000:
                w.write_table(pa.Table.from_pylist([dict(zip(COLS, r)) for r in buf], schema=schema)); nrows += len(buf); buf = []
        if buf:
            w.write_table(pa.Table.from_pylist([dict(zip(COLS, r)) for r in buf], schema=schema)); nrows += len(buf)
    stats["ops_raw"] = nrows
    json.dump(stats, open(os.path.join(ROOT, "extract-stats.json"), "w"), indent=1)
    print(stats)


if __name__ == "__main__":
    main()
