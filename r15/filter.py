#!/usr/bin/env python3
"""r15 step 5: mechanical filtering of data/r15/raw/ops-raw.parquet into the final operations table.
No model, no labelling.  Stages (each counted in data/r15/collect-report.json):
  1. petstore/template drop (spec level; rule defined below: TEMPLATE_* constants)
  2. specs with < 5 operations dropped
  3. exact spec-content dedupe (spec_sha256; keep highest stars, then repo/path order)
  4. operation dedupe on (vendor_key, method, normalised path)
  5. exclusion of every vendor already in our corpus, every exam #1-#6 vendor, and --exclude-file
     entries (e.g. the exam #7 list when it is committed).  A row is excluded if ANY of its identity
     keys (vendor_key, server/contact/logo domains, normalised domain label, normalised title,
     repo owner/name, fork-parent owner/name) matches an exclusion key (registrable domain, or
     normalised name of >= 4 characters).  Deliberately aggressive: over-exclusion is safe.
  6. cap 300 operations per vendor_key (deterministic: seeded sha256 order)
Outputs: data/r15/ops-r15.parquet, data/r15/ops-r15.csv.gz, data/r15/providers-r15.csv,
         data/r15/collect-report.json, data/r15/exclusion-keys.txt (the keys used).
Run (re-runnable, minutes):  nice -n 19 python3 r15/filter.py [--exclude-file path.txt]
    exclude-file: one vendor / domain / alias / repo per line.
"""
import argparse, csv, glob, gzip, hashlib, json, os, re, sys
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
D = os.path.join(REPO, "data", "r15")
RAW = os.path.join(D, "raw")
SEED = "r15-cap-seed-1"
CAP = 300
MIN_OPS = 5

# --- petstore / template rule (spec-level) -------------------------------------------------
TEMPLATE_TITLE_RE = re.compile(
    r"^(swagger\s+)?petstore.*$|"
    r"^(sample|example|my|test|demo|simple|todo|hello\s*world|default|new|your|awesome|basic|mock|dummy|template|"
    r"untitled|first)\s*(rest\s*)?(api|service|project|app|application|server)?(\s*v?\d+(\.\d+)*)?$")
TEMPLATE_PATHS = {"/pets", "/pets/{}", "/pet", "/pet/{}", "/pet/findbystatus", "/pet/findbytags", "/pet/{}/uploadimage",
                  "/store/order", "/store/order/{}", "/store/inventory", "/user", "/user/login", "/user/logout",
                  "/user/{}", "/user/createwitharray", "/user/createwithlist"}
TEMPLATE_PATH_MIN_HITS = 3   # >=3 template paths ...
TEMPLATE_PATH_MIN_FRAC = 0.5  # ... covering >= half of the spec's paths

GENERIC_NAMES = ids.GENERIC_TITLES | {"openapi", "swagger", "api", "apis", "docs", "doc", "backend", "frontend", "server",
                                       "service", "services", "client", "web", "app", "core", "common", "main", "master",
                                       "project", "specs", "spec", "schema", "schemas", "openapis", "microservices"}


def name_keys(s):
    """Exclusion keys from a vendor/provider string."""
    keys = set()
    for piece in re.split(r"[:\s,;|]+", s.strip().lower()):
        if not piece:
            continue
        if piece.startswith("http"):
            piece = ids.host_of(piece) or piece
        d = ids.registrable(piece) if "." in piece else None
        if d:
            keys.add(d)
            lab = ids.norm(d.split(".")[0])
            if len(lab) >= 4 and lab not in GENERIC_NAMES:
                keys.add("n:" + lab)
        n = ids.norm(piece)
        if len(n) >= 4 and n not in GENERIC_NAMES:
            keys.add("n:" + n)
    return keys


def build_exclusions(extra_file):
    keys, srcs = set(), {}
    provs = set()
    with gzip.open(os.path.join(REPO, "data/m0/mechanical.jsonl.gz"), "rt") as f:
        for l in f:
            r = json.loads(l)
            provs.add(r.get("provider") or ""); provs.add(r.get("api_key") or "")
    srcs["corpus"] = len(provs)
    n_exam = 0
    for p in glob.glob(os.path.join(REPO, "data", "**", "*"), recursive=True):
        if "/data/r15/" in p or not os.path.isfile(p):
            continue
        try:
            if os.path.getsize(p) > 400_000_000:
                continue
            if p.endswith((".csv", ".csv.gz")):
                hdr = pd.read_csv(p, nrows=0).columns
                for col in ("provider", "api_key"):
                    if col in hdr:
                        provs.update(pd.read_csv(p, usecols=[col])[col].dropna().astype(str).unique()); n_exam += 1
            elif p.endswith((".jsonl", ".jsonl.gz")):
                op = gzip.open if p.endswith(".gz") else open
                with op(p, "rt") as f:
                    for l in f:
                        if '"provider"' in l or '"api_key"' in l:
                            try:
                                r = json.loads(l)
                            except Exception:
                                continue
                            provs.add(str(r.get("provider") or "")); provs.add(str(r.get("api_key") or ""))
                n_exam += 1
        except Exception:
            continue
    # spec folder names (fresh exam specs etc.)
    for p in glob.glob(os.path.join(REPO, "data", "*specs*", "*")):
        provs.add(os.path.basename(p).rsplit(".", 1)[0])
    srcs["data_files_scanned"] = n_exam
    # domains / names mentioned in docs
    wiki = set()
    for p in glob.glob(os.path.join(REPO, "docs", "**", "*.md"), recursive=True):
        txt = open(p, errors="ignore").read().lower()
        wiki.update(re.findall(r"\b[a-z0-9][a-z0-9-]{2,}\.(?:com|io|org|net|dev|ai|co|app|cloud|so|me|sh|xyz|tech|ly)\b", txt))
    provs.update(wiki)
    srcs["docs_domains"] = len(wiki)
    # the shortlist candidates named in the PRD, always out
    extra = {"ringcentral", "baserow", "ringcentral.com", "baserow.io"}
    if extra_file:
        extra.update(l.strip() for l in open(extra_file) if l.strip() and not l.startswith("#"))
    provs.update(extra)
    for p in provs:
        keys |= name_keys(p)
    return keys, srcs


def row_keys(df):
    """identity keys per row (list of sets) built from the distinct (spec-level) identity tuples."""
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--exclude-file")
    a = ap.parse_args()
    rep = {}
    # candidates / repos / fetched stages
    cand = set()
    for l in open(os.path.join(RAW, "candidates.jsonl")):
        if l.strip():
            r = json.loads(l); cand.add((r["repo"], r["path"], r["sha"]))
    rep["candidate_files"] = len(cand)
    rep["candidate_repos"] = len({c[0] for c in cand})
    repos = [json.loads(l) for l in open(os.path.join(RAW, "repos.jsonl")) if l.strip()]
    rep["repos_looked_up"] = len(repos)
    rep["repos_missing"] = sum(1 for r in repos if r.get("missing"))
    rep["repos_permissive_licence"] = sum(1 for r in repos if r.get("kept"))
    rep["repos_licence_counts"] = pd.Series([r.get("spdx") for r in repos if r.get("kept")]).value_counts().to_dict()
    rep["repos_kept_forks"] = sum(1 for r in repos if r.get("kept") and r.get("is_fork"))
    fet = [json.loads(l) for l in open(os.path.join(RAW, "fetched.jsonl")) if l.strip()]
    rep["files_fetch_attempted"] = len(fet)
    rep["files_fetched_ok"] = sum(1 for f in fet if f["status"] == 200)
    rep["files_unique_content"] = len({f["content_sha256"] for f in fet if f["status"] == 200})
    rep["extract_stats"] = json.load(open(os.path.join(RAW, "extract-stats.json")))

    light = [c for c in pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet")).schema.names if c not in ("summary", "description")]
    df = pd.read_parquet(os.path.join(RAW, "ops-raw.parquet"), columns=light)
    rep["ops_raw"] = len(df)
    rep["specs_raw"] = df.groupby(["repo", "file_path", "spec_sha256"]).ngroups
    spec_id = df["repo"] + "\0" + df["file_path"] + "\0" + df["spec_sha256"]
    df["_spec"] = spec_id

    # 1. petstore/template
    tnorm = df["spec_title"].str.lower().str.strip()
    title_bad = tnorm.str.match(TEMPLATE_TITLE_RE) | tnorm.str.contains("petstore", regex=False)
    pnorm = df["path"].map(ids.op_path_norm)
    df["_pn"] = pnorm
    is_t = pnorm.isin(TEMPLATE_PATHS)
    g = df.assign(_t=is_t).groupby("_spec")["_t"].agg(["sum", "count"])
    path_bad_specs = set(g.index[(g["sum"] >= TEMPLATE_PATH_MIN_HITS) & (g["sum"] / g["count"] >= TEMPLATE_PATH_MIN_FRAC)])
    bad = title_bad | df["_spec"].isin(path_bad_specs)
    rep["template_rule"] = {"title_regex": TEMPLATE_TITLE_RE.pattern, "contains": "petstore",
                            "template_paths": sorted(TEMPLATE_PATHS),
                            "path_rule": ">=%d template paths covering >=%.0f%% of the spec's paths" % (TEMPLATE_PATH_MIN_HITS, TEMPLATE_PATH_MIN_FRAC * 100),
                            "ops_dropped_by_title": int(title_bad.sum()),
                            "ops_dropped_by_paths_only": int((df["_spec"].isin(path_bad_specs) & ~title_bad).sum()),
                            "specs_dropped": int(df.loc[bad, "_spec"].nunique())}
    df = df[~bad]
    rep["ops_after_template_drop"] = len(df)

    # 2. <5 ops specs
    cnt = df.groupby("_spec")["op_id"].transform("count")
    df = df[cnt >= MIN_OPS]
    rep["ops_after_min5"] = len(df)

    # 3. exact spec dedupe
    df = df.sort_values(["stars", "repo", "file_path"], ascending=[False, True, True], kind="mergesort")
    first = df.drop_duplicates("spec_sha256")[["spec_sha256", "_spec"]].set_index("spec_sha256")["_spec"]
    df = df[df["_spec"] == df["spec_sha256"].map(first)]
    rep["ops_after_spec_dedupe"] = len(df)
    rep["specs_after_spec_dedupe"] = df["_spec"].nunique()

    # 4. op dedupe
    df = df.drop_duplicates(["vendor_key", "method", "_pn"])
    rep["ops_after_op_dedupe"] = len(df)
    rep["vendors_after_op_dedupe"] = df["vendor_key"].nunique()

    # 5. exclusion
    keys, srcs = build_exclusions(a.exclude_file)
    open(os.path.join(D, "exclusion-keys.txt"), "w").write("\n".join(sorted(keys)) + "\n")
    rep["exclusion"] = dict(srcs, keys=len(keys))

    def ident(r):
        s = set()
        for v in (r.vendor_key,):
            if v.startswith(("title:", "owner:")):
                n = v.split(":", 1)[1]
                if len(n) >= 4 and n not in GENERIC_NAMES:
                    s.add("n:" + n)
            else:
                s |= name_keys(v)
        for dm in (r.servers_domains + "|" + r.contact_domain + "|" + r.logo_domain).split("|"):
            if dm:
                s |= name_keys(dm)
        for n in (r.title_norm, ids.norm(r.repo_owner), ids.norm(r.repo_name),
                  ids.norm((r.fork_parent or "/").split("/")[0]), ids.norm((r.fork_parent or "/").split("/")[-1])):
            if len(n) >= 4 and n not in GENERIC_NAMES:
                s.add("n:" + n)
        return s

    idc = df[["vendor_key", "servers_domains", "contact_domain", "logo_domain", "title_norm", "repo_owner", "repo_name", "fork_parent"]].drop_duplicates()
    hit = {}
    for r in idc.itertuples(index=False):
        hit[tuple(r)] = bool(ident(r) & keys)
    m = [hit[tuple(r)] for r in df[idc.columns].itertuples(index=False)]
    df = df[[not x for x in m]]
    rep["ops_after_exclusion"] = len(df)
    rep["vendors_after_exclusion"] = df["vendor_key"].nunique()

    # 6. cap
    df["_h"] = [hashlib.sha256((SEED + o).encode()).hexdigest() for o in df["op_id"]]
    df = df.sort_values(["vendor_key", "_h"])
    df = df.groupby("vendor_key", sort=False).head(CAP)
    rep["ops_after_cap"] = len(df)
    rep["vendors_final"] = df["vendor_key"].nunique()
    vc = df["vendor_key"].value_counts()
    rep["ops_per_vendor"] = {"min": int(vc.min()), "median": float(vc.median()), "mean": round(float(vc.mean()), 1),
                             "p90": float(vc.quantile(.9)), "max": int(vc.max()),
                             "vendors_at_cap": int((vc >= CAP).sum()), "vendors_ge5": int((vc >= 5).sum()),
                             "vendors_ge20": int((vc >= 20).sum())}
    rep["vendor_key_source_counts"] = df.groupby("vendor_key_source")["vendor_key"].nunique().to_dict()
    rep["top10_vendors"] = vc.head(10).to_dict()
    rep["target"] = {"ops": 100000, "vendors": 3000,
                     "ops_met": bool(len(df) >= 100000), "vendors_met": bool(df["vendor_key"].nunique() >= 3000)}

    # write: full columns for surviving ops
    keep = set(df["op_id"])
    pf = pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet"))
    parts = []
    for b in pf.iter_batches(batch_size=50000):
        t = b.to_pandas()
        parts.append(t[t["op_id"].isin(keep)])
    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["vendor_key", "op_id"]).reset_index(drop=True)
    out.to_parquet(os.path.join(D, "ops-r15.parquet"), index=False)
    out.to_csv(os.path.join(D, "ops-r15.csv.gz"), index=False, compression="gzip")

    # providers file
    def j(x, n=50):
        return "|".join(sorted({v for v in x if v}))[:5000]
    rows = []
    for vk, g in out.groupby("vendor_key"):
        rows.append({"vendor_key": vk, "vendor_key_source": g["vendor_key_source"].iloc[0],
                     "servers_domains": j(d for s_ in g["servers_domains"].unique() for d in s_.split("|")),
                     "contact_domains": j(d for s_ in g["contact_domain"].unique() for d in s_.split("|")),
                     "logo_domains": j(g["logo_domain"].unique()),
                     "spec_titles": j(g["spec_title"].unique()),
                     "title_norms": j(g["title_norm"].unique()),
                     "repo_owners": j(g["repo_owner"].unique()),
                     "fork_parents": j(g["fork_parent"].unique()),
                     "repo_urls": "|".join("https://github.com/" + r for r in sorted(g["repo"].unique())),
                     "ops": len(g)})
    pd.DataFrame(rows).sort_values("ops", ascending=False).to_csv(os.path.join(D, "providers-r15.csv"), index=False)
    rep["files"] = {f: os.path.getsize(os.path.join(D, f)) for f in ("ops-r15.parquet", "ops-r15.csv.gz", "providers-r15.csv")}
    json.dump(rep, open(os.path.join(D, "collect-report.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in rep.items() if not isinstance(v, (dict, list))}, indent=1))


if __name__ == "__main__":
    main()
