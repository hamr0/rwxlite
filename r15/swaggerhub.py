#!/usr/bin/env python3
"""r15 SwaggerHub public registry (QUARANTINED: download + table building only, no labelling).
Stages (resumable, progress on disk under data/r15/raw/swaggerhub/):
  list   page the registry listing (limit 100) -> listing.jsonl, progress in list-progress.json
  fetch  fetch the latest published version's spec JSON per owner/api (junk titles skipped) -> specs/, fetched.jsonl
  build  filter (template, >=5 ops, spec dedupe, op dedupe, exam #7, corpus exclusion, cap 300) and write
         data/r15/ops-r15-swaggerhub.{csv.gz,parquet}, providers-r15-swaggerhub.csv, collect-report-swaggerhub.json
Run:  nice -n 19 ionice -c3 python3 r15/swaggerhub.py {list|fetch|build}
Politeness: one request every >= 0.6 s, backoff on 429/5xx, Retry-After honoured, generic User-Agent.
"""
import hashlib, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids, extract, filter as flt

D = flt.D
SH = os.path.join(D, "raw", "swaggerhub")
SPECS = os.path.join(SH, "specs")
UA = "rwxlite-research/1.0 (API metadata study)"
LIST_URL = "https://api.swaggerhub.com/specs?specType=API&visibility=PUBLIC&state=PUBLISHED&limit=100&sort=CREATED&order=ASC&page=%d"
SPEC_URL = "https://api.swaggerhub.com/apis/%s/%s/%s"
MIN_INTERVAL = 0.6
OUT_COLS = extract.COLS + ["source"]
SRC = "swaggerhub"
ids.GENERIC_HOSTS.update({"virtserver.swaggerhub.com", "swaggerhub.com", "azure-api.net", "azure-apim.net", "azure.net"})

_last = [0.0]


def get(url, tries=8):
    """polite GET -> (status, bytes).  Backs off on 429/5xx/network errors, honours Retry-After."""
    delay = 5
    for _ in range(tries):
        w = _last[0] + MIN_INTERVAL - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                ra = e.headers.get("Retry-After")
                try:
                    wait = float(ra) if ra else delay
                except ValueError:
                    wait = delay
                time.sleep(min(max(wait, 1), 600)); delay = min(delay * 2, 300)
                continue
            return e.code, b""
        except Exception:
            time.sleep(delay); delay = min(delay * 2, 300)
    return 0, b""


def prop(entry, name):
    for p in entry.get("properties", []):
        if p.get("type") == name:
            return p.get("value", p.get("url"))
    return None


def is_junk_title(title):
    t = (title or "").lower().strip()
    return bool(flt.TEMPLATE_TITLE_RE.match(t)) or "petstore" in t


# The registry caps any one listing at 10,000 results (page 100 with limit 100 answers HTTP 500), and `offset` is
# ignored (paging is `page`, 0-based).  So the listing is taken as several 10k slices (sort x order, then
# per-owner and per-query listings for what the slices miss); the union is deduped by owner/api.
SLICES = [("CREATED", "ASC"), ("CREATED", "DESC"), ("UPDATED", "ASC"), ("UPDATED", "DESC"), ("NAME", "ASC"), ("NAME", "DESC"),
          ("TITLE", "ASC"), ("TITLE", "DESC")]
BASE = "https://api.swaggerhub.com/specs%s?specType=API&visibility=PUBLIC&state=PUBLISHED&limit=100"


def list_slice(tag, url_fn, out, prog):
    """page one slice to its end or the 10k cap; progress in list-progress.json keyed by tag."""
    st_ = prog.setdefault(tag, {"page": 0, "total": None, "done": False})
    while not st_["done"]:
        st, body = get(url_fn(st_["page"]))
        if st != 200:
            st_["done"] = True; st_["end_status"] = st
            break
        j = json.loads(body)
        st_["total"] = j["totalCount"]
        for e in j["apis"]:
            if prop(e, "X-Published") == "false" or prop(e, "X-Private") == "true":
                continue
            out.write(json.dumps({"slice": tag, "name": e.get("name"), "description": (e.get("description") or "")[:600],
                                  "url": prop(e, "Swagger"), "version": prop(e, "X-Version"),
                                  "owner": prop(e, "X-Owner"), "api": prop(e, "X-Name"),
                                  "versions": prop(e, "X-Versions"), "modified": prop(e, "X-Modified"),
                                  "created": prop(e, "X-Created"), "oas": prop(e, "X-OASVersion")}) + "\n")
        out.flush()
        st_["page"] += 1
        if not j["apis"] or st_["page"] * 100 >= j["totalCount"] or st_["page"] >= 100:
            st_["done"] = True
        json.dump(prog, open(os.path.join(SH, "list-progress.json"), "w"))
    json.dump(prog, open(os.path.join(SH, "list-progress.json"), "w"))


def cmd_list(extra=None):
    pf = os.path.join(SH, "list-progress.json")
    prog = json.load(open(pf)) if os.path.exists(pf) else {}
    out = open(os.path.join(SH, "listing.jsonl"), "a")
    for so, od in SLICES:
        list_slice("%s-%s" % (so, od), lambda pg, so=so, od=od: (BASE % "") + "&sort=%s&order=%s&page=%d" % (so, od, pg), out, prog)
        print("slice", so, od, prog["%s-%s" % (so, od)], flush=True)
    print("listing done")


def cmd_owners():
    """per-owner listings (/apis/<owner>) for owners seen with >= 2 APIs in the slices (likely the ones the 10k cap cut)."""
    pf = os.path.join(SH, "list-progress.json")
    prog = json.load(open(pf)) if os.path.exists(pf) else {}
    import collections
    cnt = collections.Counter(o for o, a in listing_unique())
    owners = sorted(o for o, n in cnt.items() if n >= 2)  # owners with 1 API in the slices are not re-listed (4+ h for ~0 gain)
    out = open(os.path.join(SH, "listing.jsonl"), "a")
    for i, o in enumerate(owners):
        tag = "owner:" + o
        if tag in prog and prog[tag]["done"]:
            continue
        list_slice(tag, lambda pg, o=o: "https://api.swaggerhub.com/apis/%s?limit=100&sort=CREATED&order=ASC&page=%d" % (urllib.parse.quote(o, safe=""), pg), out, prog)
        if i % 200 == 0:
            print("owners", i, len(owners), time.strftime("%H:%M:%S"), flush=True)
    print("owners done")


def latest_version(e):
    """latest published version: the highest-ordered '*'-marked entry of X-Versions, else the listing's own version."""
    vs = [v[1:] for v in (e.get("versions") or "").split(",") if v.startswith("*")]
    def k(v):
        return [(0, int(x)) if x.isdigit() else (1, x) for x in re.split(r"[.\-_]|(?<=\d)(?=\D)|(?<=\D)(?=\d)", v) if x]
    if vs:
        try:
            return sorted(vs, key=k)[-1]
        except Exception:
            return vs[-1]
    return e.get("version")


def listing_unique():
    seen, rows = {}, []
    for l in open(os.path.join(SH, "listing.jsonl")):
        e = json.loads(l)
        if not e.get("owner") or not e.get("api"):
            continue
        k = (e["owner"], e["api"])
        if k not in seen:
            seen[k] = e
    return seen


def cmd_fetch():
    seen = listing_unique()
    fp = os.path.join(SH, "fetched.jsonl")
    done = set()
    if os.path.exists(fp):
        for l in open(fp):
            try:
                r = json.loads(l); done.add((r["owner"], r["api"]))
            except Exception:
                pass
    todo = [(k, e) for k, e in seen.items() if k not in done and not is_junk_title(e["name"])]
    print("to fetch", len(todo), "done", len(done), flush=True)
    out = open(fp, "a")
    for i, (k, e) in enumerate(todo):
        v = latest_version(e)
        fn = "%s__%s__%s.json" % tuple(re.sub(r"[^A-Za-z0-9._-]", "_", x) for x in (k[0], k[1], v))
        st, body = get(SPEC_URL % tuple(urllib.parse.quote(x, safe="") for x in (k[0], k[1], v)))
        sha = ""
        if st == 200:
            open(os.path.join(SPECS, fn), "wb").write(body)
            sha = hashlib.sha256(body).hexdigest()
        out.write(json.dumps({"owner": k[0], "api": k[1], "version": v, "status": st, "file": fn if st == 200 else "", "sha": sha}) + "\n")
        out.flush()
        if i % 500 == 0:
            print(i, len(todo), time.strftime("%H:%M:%S"), flush=True)
    print("fetch done")


# ---------------- build ----------------
def parse_spec(d, owner, api, version, lic_default="none-stated"):
    ver = extract.s(d.get("openapi")) if "openapi" in d else extract.s(d.get("swagger"))
    paths = d.get("paths")
    if not isinstance(paths, dict) or not (ver.startswith("3") or ver.startswith("2")):
        return None
    s = extract.s
    info = d.get("info") if isinstance(d.get("info"), dict) else {}
    title = s(info.get("title"))
    contact = info.get("contact") if isinstance(info.get("contact"), dict) else {}
    logo = info.get("x-logo") if isinstance(info.get("x-logo"), dict) else {}
    lic = info.get("license")
    licence = (s(lic.get("name")) if isinstance(lic, dict) else s(lic)).strip() or "none-stated"
    servers = extract.server_urls(d)
    sdoms = sorted({x for x in (ids.domain(u) for u in servers) if x and not ids.is_generic_domain(x)})
    cd = []
    for u in (contact.get("url"), contact.get("email"), info.get("termsOfService")):
        x = ids.domain(s(u)) if u else None
        if x and not ids.is_generic_domain(x):
            cd.append(x)
    cdoms = sorted(set(cd))
    ldom = ids.domain(s(logo.get("url"))) if logo.get("url") else None
    ldom = ldom if ldom and not ids.is_generic_domain(ldom) else ""
    tn = ids.norm_title(title)
    if sdoms:
        vk, vs = sdoms[0], "server"
    elif cdoms:
        vk, vs = cdoms[0], "contact"
    elif tn and tn not in ids.GENERIC_TITLES and len(tn) >= 3:
        vk, vs = "title:" + tn, "title"
    else:
        vk, vs = "owner:" + ids.norm(owner), "owner"
    shaw = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()
    repo = "https://app.swaggerhub.com/apis/%s/%s/%s" % (owner, api, version)
    fpath = "%s/%s/%s" % (owner, api, version)
    rows = []
    for p, item in paths.items():
        if not isinstance(item, dict) or not isinstance(p, str) or not p.startswith("/"):
            continue
        for m in extract.METHODS:
            op = item.get(m) if m in item else item.get(m.upper())
            if not isinstance(op, dict):
                continue
            h = hashlib.sha256(("%s\0%s\0%s\0%s" % (fpath, shaw, m, p)).encode()).hexdigest()[:16]
            rows.append({
                "op_id": "r15s-" + h, "method": m.upper(), "path": p, "operationId": s(op.get("operationId")),
                "summary": s(op.get("summary")), "description": s(op.get("description")), "spec_title": title,
                "spec_version_field": ver, "servers": "|".join(servers), "x_logo": s(logo.get("url")),
                "contact_url": s(contact.get("url")), "contact_email": s(contact.get("email")),
                "contact_domain": "|".join(cdoms), "servers_domains": "|".join(sdoms), "logo_domain": ldom,
                "repo": repo, "repo_owner": owner, "repo_name": api, "file_path": fpath,
                "licence": licence, "is_fork": False, "fork_parent": "", "stars": None, "pushed_at": "",
                "spec_sha256": shaw, "vendor_key": vk, "vendor_key_source": vs, "title_norm": tn, "source": SRC})
    return rows


def finish(df, rep, name, extra_cols=()):
    """shared filter chain on a raw ops DataFrame with _spec/source columns.  Returns the capped frame."""
    import hashlib as H
    def per(d):
        return {k: int(v) for k, v in d["source"].value_counts().to_dict().items()}
    def perv(d):
        return {k: int(v) for k, v in d.groupby("source")["vendor_key"].nunique().to_dict().items()}
    df["_spec"] = df["source"] + "\0" + df["file_path"] + "\0" + df["spec_sha256"]
    rep["ops_raw"] = per(df); rep["specs_raw"] = {k: int(v) for k, v in df.groupby("source")["_spec"].nunique().items()}
    rep["vendors_raw"] = perv(df)
    # 1 template
    tnorm = df["spec_title"].str.lower().str.strip()
    title_bad = tnorm.str.match(flt.TEMPLATE_TITLE_RE) | tnorm.str.contains("petstore", regex=False)
    df["_pn"] = df["path"].map(ids.op_path_norm)
    g = df.assign(_t=df["_pn"].isin(flt.TEMPLATE_PATHS)).groupby("_spec")["_t"].agg(["sum", "count"])
    pb = set(g.index[(g["sum"] >= flt.TEMPLATE_PATH_MIN_HITS) & (g["sum"] / g["count"] >= flt.TEMPLATE_PATH_MIN_FRAC)])
    df = df[~(title_bad | df["_spec"].isin(pb))]
    rep["ops_after_template_drop"] = per(df); rep["vendors_after_template_drop"] = perv(df)
    # 2 min 5
    df = df[df.groupby("_spec")["op_id"].transform("count") >= flt.MIN_OPS]
    rep["ops_after_min5"] = per(df); rep["vendors_after_min5"] = perv(df)
    # 3 spec dedupe
    df = df.sort_values(["source", "file_path"], kind="mergesort")
    first = df.drop_duplicates("spec_sha256").set_index("spec_sha256")["_spec"]
    df = df[df["_spec"] == df["spec_sha256"].map(first)]
    rep["ops_after_spec_dedupe"] = per(df); rep["vendors_after_spec_dedupe"] = perv(df)
    # 4 op dedupe
    df = df.drop_duplicates(["vendor_key", "method", "_pn"])
    rep["ops_after_op_dedupe"] = per(df); rep["vendors_after_op_dedupe"] = perv(df)
    # 5a exam #7 (strict whole-label matching, filter.exam7_hits)
    ex7 = flt.load_exam7()
    cols7 = ["servers", "contact_url", "contact_email", "x_logo", "servers_domains", "contact_domain", "logo_domain",
             "spec_title", "repo", "repo_owner", "repo_name", "fork_parent"]
    d7 = df[cols7].drop_duplicates()
    h7 = {tuple(r): flt.exam7_hits(r, ex7) for r in d7.itertuples(index=False)}
    hs = [h7[tuple(r)] for r in df[cols7].itertuples(index=False)]
    drops = {}
    for hv, src in zip(hs, df["source"]):
        for v, rules in hv.items():
            e = drops.setdefault(v, {"group": ex7[v][3]}).setdefault(src, {"ops": 0, "rules": {}})
            e["ops"] += 1
            for ru in rules:
                e["rules"][ru] = e["rules"].get(ru, 0) + 1
    rep["exam7_exclusion_by_vendor_source_rule"] = drops
    df = df[[not x for x in hs]]
    rep["ops_after_exam7"] = per(df); rep["vendors_after_exam7"] = perv(df)
    # 5b corpus exclusion
    keys, srcs = flt.build_exclusions(None)
    rep["exclusion"] = dict(srcs, keys=len(keys))
    def ident(r):
        k = set()
        if r.vendor_key.startswith(("title:", "owner:")):
            n = r.vendor_key.split(":", 1)[1]
            if len(n) >= 4 and n not in flt.GENERIC_NAMES:
                k.add("n:" + n)
        else:
            k |= flt.name_keys(r.vendor_key)
        for dm in (r.servers_domains + "|" + r.contact_domain + "|" + r.logo_domain).split("|"):
            if dm:
                k |= flt.name_keys(dm)
        for n in (r.title_norm, ids.norm(r.repo_owner), ids.norm(r.repo_name)):
            if len(n) >= 4 and n not in flt.GENERIC_NAMES:
                k.add("n:" + n)
        return k
    idc = df[["vendor_key", "servers_domains", "contact_domain", "logo_domain", "title_norm", "repo_owner", "repo_name"]].drop_duplicates()
    hm = {tuple(r): sorted(ident(r) & keys) for r in idc.itertuples(index=False)}
    m = [hm[tuple(r)] for r in df[idc.columns].itertuples(index=False)]
    seen = pd.Series([bool(x) for x in m], index=df.index)
    sd = df[seen].assign(_k=[x[0] for x in m if x])
    rep["already_in_corpus_dropped"] = {"vendors_by_source": perv(sd), "ops_by_source": per(sd),
                                        "vendors_total": int(sd["vendor_key"].nunique()),
                                        "vendor_keys": sorted(sd["vendor_key"].unique())[:3000]}
    df = df[~seen]
    rep["ops_after_corpus_exclusion"] = per(df); rep["vendors_after_corpus_exclusion"] = perv(df)
    # 6 cap
    df = df.assign(_h=[H.sha256((flt.SEED + o).encode()).hexdigest() for o in df["op_id"]])
    df = df.sort_values(["vendor_key", "_h"]).groupby("vendor_key", sort=False).head(flt.CAP)
    rep["ops_after_cap"] = per(df); rep["vendors_final"] = perv(df)
    rep["ops_final_total"] = len(df); rep["vendors_final_total"] = int(df["vendor_key"].nunique())
    vc = df["vendor_key"].value_counts()
    rep["top10_vendors"] = {k: int(v) for k, v in vc.head(10).items()}
    rep["ops_per_vendor"] = {"min": int(vc.min()), "median": float(vc.median()), "max": int(vc.max()), "vendors_at_cap": int((vc >= flt.CAP).sum())}
    return df


def write_outputs(df, rep, tag, cols):
    out = df[cols].sort_values(["vendor_key", "op_id"]).reset_index(drop=True)
    out.to_parquet(os.path.join(D, "ops-r15-%s.parquet" % tag), index=False)
    out.to_csv(os.path.join(D, "ops-r15-%s.csv.gz" % tag), index=False, compression="gzip")
    def j(x):
        return "|".join(sorted({v for v in x if v}))[:5000]
    rows = []
    for vk, g in out.groupby("vendor_key"):
        rows.append({"vendor_key": vk, "vendor_key_source": g["vendor_key_source"].iloc[0], "source": "|".join(sorted(g["source"].unique())),
                     "servers_domains": j(d for s_ in g["servers_domains"].unique() for d in s_.split("|")),
                     "contact_domains": j(d for s_ in g["contact_domain"].unique() for d in s_.split("|")),
                     "logo_domains": j(g["logo_domain"].unique()), "spec_titles": j(g["spec_title"].unique()),
                     "title_norms": j(g["title_norm"].unique()), "repo_owners": j(g["repo_owner"].unique()),
                     "repo_urls": "|".join(sorted(g["repo"].unique()))[:5000], "ops": len(g)})
    pd.DataFrame(rows).sort_values("ops", ascending=False).to_csv(os.path.join(D, "providers-r15-%s.csv" % tag), index=False)
    rep["files"] = {f: os.path.getsize(os.path.join(D, f)) for f in ("ops-r15-%s.parquet" % tag, "ops-r15-%s.csv.gz" % tag, "providers-r15-%s.csv" % tag)}
    json.dump(rep, open(os.path.join(D, "collect-report-%s.json" % tag), "w"), indent=1, default=str)


def cmd_build():
    seen = listing_unique()
    rep = {"listing_lines": sum(1 for _ in open(os.path.join(SH, "listing.jsonl"))), "listing_unique_owner_api": len(seen)}
    rep["listing_skipped_junk_title"] = sum(1 for e in seen.values() if is_junk_title(e["name"]))
    ok, fails, rows = 0, {}, []
    for l in open(os.path.join(SH, "fetched.jsonl")):
        r = json.loads(l)
        if r["status"] != 200:
            fails[str(r["status"])] = fails.get(str(r["status"]), 0) + 1
            continue
        try:
            d = json.load(open(os.path.join(SPECS, r["file"]), encoding="utf-8"))
            rr = parse_spec(d, r["owner"], r["api"], r["version"]) if isinstance(d, dict) else None
        except Exception:
            rr = None
        if rr is None:
            fails["unparseable"] = fails.get("unparseable", 0) + 1
            continue
        ok += 1; rows += rr
    rep["specs_fetched_ok"] = len(os.listdir(SPECS)); rep["specs_parsed"] = ok; rep["fetch_failures"] = fails
    df = pd.DataFrame(rows)
    rep["ops_raw_total"] = len(df)
    df = finish(df, rep, SRC)
    write_outputs(df, rep, "swaggerhub", OUT_COLS)
    print(json.dumps({k: v for k, v in rep.items() if not isinstance(v, (dict, list))}, indent=1))


if __name__ == "__main__":
    {"list": cmd_list, "owners": cmd_owners, "fetch": cmd_fetch, "build": cmd_build}[sys.argv[1]]()
