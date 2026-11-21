#!/usr/bin/env python3
"""r16 GitHub collection, filter + new-vendor + exam #8 freeze + cap (table work only; no labelling, no model).

Input : data/r16/raw/{candidates,repos,fetched}.jsonl, ops-raw.parquet, extract-stats.json (r16/search, licences, fetch, extract)
Output: data/r16/ops-r16-github.{csv.gz,parquet}, vendors-r16-github.csv, collect-report-github.json
Stages (each counted in the report; ops / specs / vendors):
  r15 rules : template/petstore drop -> spec min 5 ops -> exact spec dedupe -> op dedupe (vendor_key+method+path)
  quality   : has_text -> junk-domain flag -> non-HTTP method -> rpc flag -> lang == en (r15/master.py lang_signal)
  exam #8   : hard freeze (r16/pick_dev.py matcher, whole labels + substring audit) incl. mirror copies (same sha, near-dup)
  new vendor: spec sha in r15 master -> vendor_key in master -> registrable domain in master -> R13 tokens ->
              r15 exclusion keys / exam #7 list -> rwxmap-flagged spec -> r16 dev pick -> near-dup spec of a master spec ->
              cross-source duplicate op (method+path+operationId+summary of any master row)
  dedupe    : near-duplicate spec groups inside the r16 set (Jaccard >= 0.8 on method+path sets) keep the primary spec only
  cap       : 300 ops per vendor_key, seeded sha256 order (seed 16)
Reuses r15 code unchanged by import (r15/master.py, r15/filter.py, r15/ids.py); nothing in r15/ is modified.
Run: nice -n 19 python3 r16/filter_github.py
"""
import collections, csv, gzip, hashlib, importlib.util, json, os, re, sys, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "r15"))
sys.path.insert(0, HERE)
import ids  # r15/ids.py (r16/ids.py is a byte copy apart from the docstring)
import opkey  # exact operation key (tuples; see its docstring for why the first version with hashes matched nothing)


def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


M = load("r15master", os.path.join(REPO, "r15", "master.py"))
F = load("r15filter", os.path.join(REPO, "r15", "filter.py"))
P = load("r16pickdev", os.path.join(HERE, "pick_dev.py"))

D = os.path.join(REPO, "data")
RAW = os.path.join(D, "r16", "raw")
OUT = os.path.join(D, "r16")
MASTER = os.path.join(D, "r15", "master", "ops-r15-master.parquet")
SEED, CAP, MIN_OPS = "r16-cap-seed-16", 300, 5
t0 = time.time()
REP = {"stages": []}


def log(*a):
    print("[%6.0fs]" % (time.time() - t0), *a, flush=True)


def stage(name, df, note=None):
    s = {"stage": name, "ops": int(len(df)), "specs": int(df["_spec"].nunique()), "vendors": int(df["vendor_key"].nunique())}
    if note:
        s["note"] = note
    REP["stages"].append(s)
    log(name, s["ops"], "ops", s["specs"], "specs", s["vendors"], "vendors")


def regdom_label(d):
    return d.split(".")[0] if d else ""


def main():
    # ------------------------------------------------------------------ search / licence / fetch counts
    cand = set()
    for l in open(os.path.join(RAW, "candidates.jsonl")):
        if l.strip():
            r = json.loads(l); cand.add((r["repo"], r["path"], r["sha"]))
    repos = [json.loads(l) for l in open(os.path.join(RAW, "repos.jsonl")) if l.strip()]
    fet = [json.loads(l) for l in open(os.path.join(RAW, "fetched.jsonl")) if l.strip()]
    elig_set = {r["repo"] for r in repos if not r.get("kept") and not r.get("missing") and not r.get("is_fork")}
    lic = collections.Counter((r.get("spdx") or "none") if not r.get("missing") else "(missing)" for r in repos)
    elig = [r for r in repos if not r.get("kept") and not r.get("missing") and not r.get("is_fork")]
    REP["search"] = {"candidate_files": len(cand), "candidate_repos": len({c[0] for c in cand}),
                     "note": "r15 data/r15/raw was deleted 2026-11-19, so the search was re-run; counts differ from r15's 139,871 files / 87,363 repos"}
    REP["licence_lookup"] = {
        "repos_looked_up": len(repos), "repos_missing": sum(1 for r in repos if r.get("missing")),
        "repos_permissive_licence_fetched_by_r15": sum(1 for r in repos if r.get("kept")),
        "repos_forks_excluded": sum(1 for r in repos if r.get("is_fork") and not r.get("kept") and not r.get("missing")),
        "repos_forks_among_permissive": sum(1 for r in repos if r.get("is_fork") and r.get("kept")),
        "repos_to_fetch": len(elig), "files_to_fetch_candidates": sum(1 for c in cand if c[0] in elig_set),
        "licence_counts_all_repos_top": dict(lic.most_common(25)), "licence_none_means": "no licence file detected by GitHub (spdx null)"}
    REP["fetch"] = {"files_attempted": len(fet), "ok": sum(1 for f in fet if f["status"] == 200),
                    "status_counts": dict(collections.Counter(str(f["status"]) for f in fet)),
                    "unique_content": len({f["content_sha256"] for f in fet if f["status"] == 200})}
    REP["extract"] = json.load(open(os.path.join(RAW, "extract-stats.json")))

    # ------------------------------------------------------------------ raw ops (light) + stages 1-4 (r15 rules)
    light = [c for c in pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet")).schema.names if c not in ("summary", "description")]
    df = pd.read_parquet(os.path.join(RAW, "ops-raw.parquet"), columns=light)
    df["_spec"] = df["repo"] + "\0" + df["file_path"] + "\0" + df["spec_sha256"]
    stage("ops_raw", df)

    # exam #8 hits on ALL raw specs (before any dedupe), so mirrors cannot slip through a dedupe
    ID8 = ["vendor_key", "servers", "servers_domains", "contact_domain", "logo_domain", "contact_url", "spec_title", "title_norm",
           "repo", "repo_owner", "repo_name", "file_path"]
    sp_raw = df.drop_duplicates("_spec")[["_spec", "spec_sha256"] + ID8].copy()
    sp_raw["repo_url"] = "https://github.com/" + sp_raw["repo"]
    hits_raw = {}
    for r in sp_raw.to_dict("records"):
        w, s = P.hits8(r)
        if w or s:
            hits_raw[r["_spec"]] = (w, s)
    ex8_sha = {sp_raw.set_index("_spec").at[k, "spec_sha256"] for k in hits_raw}
    log("exam8 raw spec hits", len(hits_raw))

    tnorm = df["spec_title"].str.lower().str.strip()
    title_bad = tnorm.str.match(F.TEMPLATE_TITLE_RE) | tnorm.str.contains("petstore", regex=False)
    df["_pn"] = df["path"].map(ids.op_path_norm)
    g = df.assign(_t=df["_pn"].isin(F.TEMPLATE_PATHS)).groupby("_spec")["_t"].agg(["sum", "count"])
    pbs = set(g.index[(g["sum"] >= F.TEMPLATE_PATH_MIN_HITS) & (g["sum"] / g["count"] >= F.TEMPLATE_PATH_MIN_FRAC)])
    bad = title_bad | df["_spec"].isin(pbs)
    REP["template_rule"] = {"ops_dropped_by_title": int(title_bad.sum()), "ops_dropped_by_paths_only": int((df["_spec"].isin(pbs) & ~title_bad).sum()),
                            "specs_dropped": int(df.loc[bad, "_spec"].nunique())}
    df = df[~bad]; stage("after_template_petstore_drop", df)
    df = df[df.groupby("_spec")["op_id"].transform("count") >= MIN_OPS]; stage("after_spec_min5_ops", df)
    df = df.sort_values(["stars", "repo", "file_path"], ascending=[False, True, True], kind="mergesort")
    first = df.drop_duplicates("spec_sha256")[["spec_sha256", "_spec"]].set_index("spec_sha256")["_spec"]
    df = df[df["_spec"] == df["spec_sha256"].map(first)]; stage("after_spec_dedupe", df)
    df = df.drop_duplicates(["vendor_key", "method", "_pn"]); stage("after_op_dedupe", df)

    # ------------------------------------------------------------------ text + language (r15 master functions)
    keep = set(df["op_id"])
    parts = []
    for b in pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet")).iter_batches(batch_size=50000, columns=["op_id", "summary", "description"]):
        t = b.to_pandas(); parts.append(t[t["op_id"].isin(keep)])
    txt = pd.concat(parts, ignore_index=True)
    df = df.merge(txt, on="op_id", how="left")
    df["method_norm"] = df["method"].str.strip().str.upper()
    df["path_norm"] = df["path"].str.replace(r"\{[^}]*\}", "{}", regex=True).str.lower().str.rstrip("/").replace("", "/")
    df["text_clean"] = [M.make_text(a, b) for a, b in zip(df["summary"], df["description"])]
    df["has_text"] = (df["summary"].str.strip() != "") | (df["description"].str.strip() != "") | (df["operationId"].str.strip() != "")
    sig = [M.lang_signal(t if t else o) for t, o in zip(df["text_clean"], df["operationId"])]
    df["_l"] = [s[0] for s in sig]; df["_strong"] = [s[1] for s in sig]
    strong = df[df["_strong"] & (df["_l"] != "")]
    maj = strong.groupby("spec_sha256")["_l"].agg(lambda s: s.value_counts().index[0])
    sm = df["spec_sha256"].map(maj)
    df["lang"] = np.where(df["_strong"], df["_l"], np.where((df["_l"] == "en") & sm.notna(), sm, np.where(df["_l"] == "", "other", df["_l"])))
    df["lang"] = df["lang"].replace("", "other")
    df["vendor_id"] = df["vendor_key"]
    df["vendor_kind"] = np.where(df["vendor_key"].str.startswith("title:"), "title", np.where(df["vendor_key"].str.startswith("owner:"), "owner", "domain"))
    df["source"] = "github"; df["api_style"] = ""
    dom = df["vendor_key"].where(df["vendor_kind"] == "domain", "")
    df["_junk"] = dom.map(M.junk_domain)
    df["_spec_ops"] = df.groupby("_spec")["op_id"].transform("size")
    df["flags"], _ = M.build_flags(df)
    REP["lang_all_after_e"] = df["lang"].value_counts().to_dict()
    REP["flag_counts_after_e"] = {f: int(df["flags"].str.contains(f).sum()) for f in
                                  ["junk_domain", "no_text", "rpc", "non_http_method", "huge_spec", "odd_path", "lorem", "placeholder_text", "autogen_opid_only", "test_endpoint"]}
    log("text/lang/flags done")
    df_e = df  # all languages; used for near-dup grouping

    # quality filters, counted one after another
    q = df[df["has_text"]]; stage("after_has_text", q)
    q = q[~q["flags"].str.contains("junk_domain")]; stage("after_junk_domain_flag", q)
    q = q[~q["flags"].str.contains("non_http_method")]; stage("after_non_http_method", q)
    q = q[~q["flags"].str.contains(r"(?:^|;)rpc(?:;|$)")]; stage("after_rpc_flag", q)
    REP["lang_before_filter"] = q["lang"].value_counts().to_dict()
    q = q[q["lang"] == "en"]; stage("after_lang_en", q)

    # ------------------------------------------------------------------ master side
    mcols = ["op_id", "vendor_id", "vendor_key", "vendor_kind", "spec_sha256", "method", "path", "operationId", "summary", "servers_domains",
             "contact_domain", "logo_domain", "method_norm", "path_norm", "spec_title", "title_norm", "repo", "repo_owner", "repo_name",
             "servers", "contact_url", "file_path"]
    mast = pd.read_parquet(MASTER, columns=mcols)
    log("master", len(mast))
    m_vendors = set(mast["vendor_id"]) | set(mast["vendor_key"])
    m_shas = set(mast["spec_sha256"])

    def doms(*cols):
        s = set()
        for c in cols:
            for v in mast[c].dropna().unique():
                s.update(x for x in v.split("|") if x)
        return s
    m_dom = {v for v in set(mast["vendor_id"][mast["vendor_kind"] == "domain"]) if "." in v and ":" not in v} | doms("servers_domains", "contact_domain", "logo_domain")
    r13 = {l.strip() for l in open(os.path.join(D, "round13", "vendors-r13-seen.txt")) if l.strip()}
    exkeys = {l.strip() for l in open(os.path.join(D, "r15", "exclusion-keys.txt")) if l.strip()}
    flagged = {l.strip().split(",")[0].split()[0] for l in open(os.path.join(D, "r15", "rwxmap-flagged.txt")) if l.strip() and not l.startswith("#")}
    dev_v = {r["vendor_key"] for r in csv.DictReader(open(os.path.join(D, "r16", "dev", "dev-vendors.csv"), newline=""))}
    dev_sha, dev_op = set(), set()
    with gzip.open(os.path.join(D, "r16", "dev", "dev-ops.csv.gz"), "rt", newline="") as f:
        csv.field_size_limit(10**9)
        for r in csv.DictReader(f):
            dev_sha.add(r["spec_sha256"]); dev_op.add(r["op_id"])
    ex7 = F.load_exam7()
    REP["new_vendor_inputs"] = {"master_ops": len(mast), "master_vendors": len(m_vendors), "master_specs": len(m_shas), "master_domains": len(m_dom),
                                "r13_tokens": len(r13), "r15_exclusion_keys": len(exkeys), "rwxmap_flagged_specs": len(flagged),
                                "dev_vendors": len(dev_v), "dev_specs": len(dev_sha), "dev_ops": len(dev_op)}

    # ------------------------------------------------------------------ near-dup groups: r16 (post-E, all langs) + master
    comb = pd.concat([df_e[["spec_sha256", "method_norm", "path_norm"]], mast[["spec_sha256", "method_norm", "path_norm"]]], ignore_index=True)
    sg = M.spec_groups(comb)
    log("spec groups", len(set(sg.values())), "specs in groups", len(sg))
    del comb
    # exam #8 seeds from the master (those specs are already inside the master sheet)
    ex8_master_sha = set()
    ms = mast.drop_duplicates("spec_sha256")
    for r in ms.to_dict("records"):
        r["repo_url"] = "https://github.com/" + r["repo"] if r["repo"] else ""
        w, s = P.hits8(r)
        if w or s:
            ex8_master_sha.add(r["spec_sha256"])
    REP["exam8_master_seed_specs"] = len(ex8_master_sha)
    ex8_groups = {sg[s] for s in (ex8_sha | ex8_master_sha) if s in sg}
    m_groups = {sg[s] for s in m_shas if s in sg}

    # ------------------------------------------------------------------ exam #8 freeze (spec level, then drop)
    q = q.copy()
    q["_ex8_own"] = q["_spec"].map(lambda s: s in hits_raw)
    q["_ex8_sha"] = q["spec_sha256"].isin(ex8_sha) & ~q["_ex8_own"]
    q["_ex8_grp"] = q["spec_sha256"].map(lambda s: sg.get(s, -1) in ex8_groups) & ~q["_ex8_own"] & ~q["_ex8_sha"]
    dropped8 = q[q["_ex8_own"] | q["_ex8_sha"] | q["_ex8_grp"]]
    d8 = []
    for sp, g_ in dropped8.groupby("_spec"):
        r0 = g_.iloc[0]
        w, s = hits_raw.get(sp, (set(), set()))
        d8.append({"repo": r0["repo"], "file_path": r0["file_path"], "title": r0["spec_title"], "vendor_key": r0["vendor_key"], "ops": len(g_),
                   "how": "own_hit" if sp in hits_raw else ("same_sha256_mirror" if g_["_ex8_sha"].iloc[0] else "near_duplicate_of_exam8_spec"),
                   "exam8_whole_label": sorted(w), "exam8_substring_only": sorted(s - w) if sp in hits_raw else []})
    REP["exam8"] = {"raw_specs_hit": len(hits_raw), "raw_hit_specs_list": [
        {"repo": sp_raw.set_index("_spec").at[k, "repo"], "file_path": sp_raw.set_index("_spec").at[k, "file_path"], "whole": sorted(w), "substring_only": sorted(s - w)}
        for k, (w, s) in hits_raw.items()],
        "ops_dropped_at_this_stage": int(len(dropped8)), "specs_dropped_at_this_stage": len(d8),
        "ops_by_how": dropped8.assign(h=np.where(dropped8["_ex8_own"], "own_hit", np.where(dropped8["_ex8_sha"], "same_sha256_mirror", "near_duplicate_of_exam8_spec"))).groupby("h").size().to_dict(),
        "dropped_specs": d8}
    q = q[~(q["_ex8_own"] | q["_ex8_sha"] | q["_ex8_grp"])]
    stage("after_exam8_freeze", q, "own hits (whole label/domain/repo + substring audit) + same-sha mirrors + near-dup (Jaccard>=0.8) copies")

    # ------------------------------------------------------------------ new-vendor rule (spec-level flags, applied sequentially)
    IDC = ["vendor_key", "servers_domains", "contact_domain", "logo_domain", "title_norm", "repo_owner", "repo_name", "fork_parent",
           "servers", "contact_url", "contact_email", "x_logo", "spec_title", "repo"]
    spec_tbl = q.drop_duplicates("_spec")
    flag = {}
    for s in spec_tbl[["_spec", "spec_sha256", "vendor_key", "vendor_kind"] + IDC[1:]].to_dict("records"):
        dset = {d for d in (s["servers_domains"] + "|" + s["contact_domain"] + "|" + s["logo_domain"]).split("|") if d}
        if s["vendor_kind"] == "domain":
            dset.add(s["vendor_key"])
        labs = set()
        if s["vendor_kind"] == "domain":
            labs.add(regdom_label(s["vendor_key"]))
        elif s["vendor_kind"] == "title":
            labs.add(s["title_norm"])
        labs |= {regdom_label(d) for d in dset}
        ident = F.name_keys(s["vendor_key"]) if s["vendor_kind"] == "domain" else set()
        if s["vendor_kind"] != "domain":
            n = s["vendor_key"].split(":", 1)[1]
            if len(n) >= 4 and n not in F.GENERIC_NAMES:
                ident.add("n:" + n)
        for dm in dset:
            ident |= F.name_keys(dm)
        for n in (s["title_norm"], ids.norm(s["repo_owner"]), ids.norm(s["repo_name"]), ids.norm((s["fork_parent"] or "/").split("/")[0]), ids.norm((s["fork_parent"] or "/").split("/")[-1])):
            if len(n) >= 4 and n not in F.GENERIC_NAMES:
                ident.add("n:" + n)
        flag[s["_spec"]] = {
            "sha_in_master": s["spec_sha256"] in m_shas,
            "vendor_in_master": s["vendor_key"] in m_vendors,
            "domain_in_master": bool(dset & m_dom),
            "domain_in_master_vendor_server_only": bool(({s["vendor_key"]} | {d for d in s["servers_domains"].split("|") if d}) & m_dom),
            "r13_token": bool(labs & r13),
            "r15_exclusion_key": bool(ident & exkeys),
            "exam7_list": bool(F.exam7_hits(type("R", (), s)(), ex7)),
            "rwxmap_flagged": s["spec_sha256"] in flagged,
            "dev_pick": s["vendor_key"] in dev_v or s["spec_sha256"] in dev_sha,
            "near_dup_of_master_spec": sg.get(s["spec_sha256"], -1) in m_groups,
        }
    fl = pd.DataFrame.from_dict(flag, orient="index")
    log("new-vendor flags built", len(fl))
    REP["new_vendor_independent_hits_ops"] = {}
    q = q.copy()
    for c in fl.columns:
        q["_f_" + c] = q["_spec"].map(fl[c]).fillna(False).astype(bool)
        REP["new_vendor_independent_hits_ops"][c] = int(q["_f_" + c].sum())
    order = [("sha_in_master", "after_nv_spec_sha_in_master"), ("vendor_in_master", "after_nv_vendor_key_in_master"),
             ("domain_in_master", "after_nv_registrable_domain_in_master"), ("r13_token", "after_nv_r13_token"),
             ("r15_exclusion_key", "after_nv_r15_exclusion_keys"), ("exam7_list", "after_nv_exam7_list"),
             ("rwxmap_flagged", "after_nv_rwxmap_flagged"), ("dev_pick", "after_nv_r16_dev_pick"),
             ("near_dup_of_master_spec", "after_nv_near_dup_of_master_spec")]
    REP["domain_rule_note"] = {"ops_hit_vendor_key_or_servers_only": int(q["_spec"].map(fl["domain_in_master_vendor_server_only"]).fillna(False).astype(bool).sum()),
                               "note": "applied rule also includes contact/logo domains (stricter); the vendor_key/servers-only subset is listed for comparison"}
    for c, name in order:
        q = q[~q["_f_" + c]]
        stage(name, q)

    # cross-source duplicate ops: same method+path+operationId+summary as any master row
    # Fixed 2026-11-21: the first version hashed "method\0path\0operationId\0summary" with pandas hash_pandas_object, which stops at the first NUL
    # (so the master side was hashed on the method alone) while the object-dtype r16 side lost its NULs; the two never agreed and 0 ops were dropped
    # (cause and proof: PRD "Cleaning" section). The key is now a python tuple (r16/opkey.py).
    k_m = set(opkey.k1(mast))
    xd = np.array([k in k_m for k in opkey.k1(q)])
    REP["cross_source_dup_ops_dropped"] = int(xd.sum())
    q = q[~xd]; stage("after_nv_cross_source_duplicate_ops", q)
    REP["new_vendor_note"] = "per-stage counts are sequential; 'new_vendor_independent_hits_ops' counts each rule alone on the post-exam8 table"

    # ------------------------------------------------------------------ near-duplicate spec groups inside r16 (keep primary)
    stats = q.groupby("spec_sha256").agg(tl=("text_clean", lambda s: int(s.str.len().sum())))
    grp = {s: sg[s] for s in stats.index if s in sg}
    sdf = pd.DataFrame({"sha": list(grp), "g": list(grp.values())})
    sdf["tl"] = sdf["sha"].map(stats["tl"])
    sdf = sdf.sort_values(["g", "tl", "sha"], ascending=[True, False, True])
    primary = sdf.groupby("g")["sha"].first().to_dict()
    nd = q["spec_sha256"].map(lambda s: s in grp and primary[grp[s]] != s)
    REP["inner_near_dup"] = {"ops_dropped": int(nd.sum()), "specs_dropped": int(q.loc[nd, "_spec"].nunique()),
                             "groups_with_dropped_members": int(q.loc[nd, "spec_sha256"].map(grp).nunique())}
    q = q[~nd]; stage("after_inner_near_duplicate_specs", q)
    q = q.copy()
    q["spec_group"] = q["spec_sha256"].map(lambda s: "sg-%d" % sg[s] if s in sg else "")
    q["dup_of"] = ""; q["also_in"] = ""
    pre_cap = q

    # ------------------------------------------------------------------ cap (seed 16)
    q = q.copy()
    q["_h"] = [hashlib.sha256((SEED + o).encode()).hexdigest() for o in q["op_id"]]
    q = q.sort_values(["vendor_key", "_h"]).groupby("vendor_key", sort=False).head(CAP)
    stage("after_cap_300_per_vendor", q)

    # ------------------------------------------------------------------ outputs
    cols = ["op_id", "method", "path", "operationId", "summary", "description", "spec_title", "spec_version_field", "servers", "x_logo",
            "contact_url", "contact_email", "contact_domain", "servers_domains", "logo_domain", "repo", "repo_owner", "repo_name", "file_path",
            "licence", "is_fork", "fork_parent", "stars", "pushed_at", "spec_sha256", "vendor_key", "vendor_key_source", "title_norm",
            "visibility", "deprecated", "repo_url", "folder", "publisher", "website", "privacy_url", "api_style", "product",
            "source", "method_norm", "path_norm", "vendor_id", "vendor_kind", "lang", "has_text", "text_clean", "flags", "spec_group", "dup_of", "also_in"]
    out = q.copy()
    out["repo_url"] = "https://github.com/" + out["repo"]
    for c in cols:
        if c not in out:
            out[c] = ""
    out = out[cols].sort_values(["vendor_id", "op_id"]).reset_index(drop=True)
    out.to_csv(os.path.join(OUT, "ops-r16-github.csv.gz"), index=False, compression="gzip")
    try:
        o2 = out.astype({c: str for c in cols if c not in ("is_fork", "stars", "has_text")})
        o2.to_parquet(os.path.join(OUT, "ops-r16-github.parquet"), index=False)
    except Exception as e:
        REP["parquet_error"] = str(e)

    def j(x):
        return "|".join(sorted({v for v in x if v}))[:5000]
    rows = []
    for vk, g_ in out.groupby("vendor_id"):
        rows.append({"vendor_key": vk, "vendor_kind": g_["vendor_kind"].iloc[0], "ops": len(g_), "specs": g_["spec_sha256"].nunique(),
                     "servers_domains": j(d for s_ in g_["servers_domains"].unique() for d in s_.split("|")),
                     "contact_domains": j(d for s_ in g_["contact_domain"].unique() for d in s_.split("|")),
                     "logo_domains": j(g_["logo_domain"].unique()), "spec_titles": j(g_["spec_title"].unique()),
                     "title_norms": j(g_["title_norm"].unique()), "repo_owners": j(g_["repo_owner"].unique()),
                     "licences": j(g_["licence"].unique()),
                     "repo_urls": "|".join(sorted(g_["repo_url"].unique())), "spec_sha256s": "|".join(sorted(g_["spec_sha256"].unique()))})
    pd.DataFrame(rows).sort_values("ops", ascending=False).to_csv(os.path.join(OUT, "vendors-r16-github.csv"), index=False)

    # ------------------------------------------------------------------ diversity
    vc = out["vendor_id"].value_counts()
    tot = len(out)
    REP["final"] = {"ops": tot, "vendors": int(len(vc)), "specs": int(out["spec_sha256"].nunique()), "repos": int(out["repo"].nunique())}
    REP["diversity"] = {
        "ops_per_vendor": {"min": int(vc.min()), "median": float(vc.median()), "mean": round(float(vc.mean()), 1), "p90": float(vc.quantile(.9)), "p99": float(vc.quantile(.99)),
                           "max": int(vc.max()), "vendors_at_cap": int((vc >= CAP).sum()), "vendors_lt5": int((vc < 5).sum()), "vendors_ge5": int((vc >= 5).sum()),
                           "vendors_ge20": int((vc >= 20).sum()), "vendors_ge100": int((vc >= 100).sum())},
        "vendor_size_histogram": {"1-4": int((vc < 5).sum()), "5-9": int(((vc >= 5) & (vc < 10)).sum()), "10-19": int(((vc >= 10) & (vc < 20)).sum()),
                                  "20-49": int(((vc >= 20) & (vc < 50)).sum()), "50-99": int(((vc >= 50) & (vc < 100)).sum()),
                                  "100-299": int(((vc >= 100) & (vc < 300)).sum()), "300": int((vc >= 300).sum())},
        "method_mix": (out["method_norm"].value_counts() / tot).round(4).to_dict(),
        "share_top10_vendors": round(float(vc.head(10).sum() / tot), 4), "share_top100_vendors": round(float(vc.head(100).sum() / tot), 4),
        "top10_vendors": vc.head(10).to_dict(),
        "vendor_kind_vendors": out.groupby("vendor_kind")["vendor_id"].nunique().to_dict(), "vendor_kind_ops": out["vendor_kind"].value_counts().to_dict(),
        "licence_ops": out["licence"].value_counts().head(15).to_dict(),
        "top_registrable_domains_by_ops": out.loc[out["vendor_kind"] == "domain", "vendor_id"].value_counts().head(25).to_dict(),
        "tld_vendors_top": pd.Series([v.rsplit(".", 1)[-1] for v in out.loc[out["vendor_kind"] == "domain", "vendor_id"].unique()]).value_counts().head(15).to_dict(),
    }
    words = collections.Counter()
    for t in out.drop_duplicates("spec_sha256")["spec_title"]:
        words.update({w for w in re.findall(r"[a-z]{4,}", t.lower())} - {"swagger", "openapi", "service", "services", "specification", "documentation", "version", "this", "with", "your"})
    REP["diversity"]["top_title_words_by_specs"] = dict(words.most_common(40))

    # near-duplicate / template families on the pre-cap table: same title_norm across many repos
    sp = pre_cap.drop_duplicates("spec_sha256")
    fam = sp.groupby("title_norm").agg(repos=("repo", "nunique"), specs=("spec_sha256", "nunique"), vendors=("vendor_key", "nunique"), example=("spec_title", "first"),
                                       owners=("repo_owner", "nunique"))
    fam = fam[fam.index != ""]
    ops_by_fam = pre_cap.groupby("title_norm").size()
    fam["ops_precap"] = ops_by_fam
    fam["ops_final"] = out.groupby("title_norm").size()
    fam = fam.sort_values(["repos", "specs"], ascending=False)
    pk = pre_cap.groupby("spec_sha256").apply(lambda g_: frozenset(zip(g_["method_norm"], g_["path_norm"])), include_groups=False)
    famrows = []
    for tn, r in fam.head(40).iterrows():
        shas = sp.loc[sp["title_norm"] == tn, "spec_sha256"].tolist()
        base = pk[shas[0]]
        js = [len(base & pk[s]) / max(1, len(base | pk[s])) for s in shas[1:]]
        mean_j = float(np.mean(js)) if js else 1.0
        famrows.append({"title_norm": tn, "example_title": r["example"], "repos": int(r["repos"]), "specs": int(r["specs"]), "vendors": int(r["vendors"]),
                        "owners": int(r["owners"]), "ops_precap": int(r["ops_precap"]), "ops_final": int(r["ops_final"] if pd.notna(r["ops_final"]) else 0),
                        "mean_pathset_jaccard_vs_first": round(mean_j, 2),
                        "looks_like_one_template_copied": bool(r["repos"] >= 10 and mean_j >= 0.5)})
    REP["title_families_top"] = famrows
    REP["title_families_summary"] = {"families_ge10_repos": int((fam["repos"] >= 10).sum()), "families_ge5_repos": int((fam["repos"] >= 5).sum()),
                                     "ops_final_in_families_ge10_repos": int(fam.loc[fam["repos"] >= 10, "ops_final"].fillna(0).sum()),
                                     "ops_final_in_template_like_families": int(sum(f["ops_final"] for f in famrows if f["looks_like_one_template_copied"]))}
    REP["seconds"] = round(time.time() - t0)
    json.dump(REP, open(os.path.join(OUT, "collect-report-github.json"), "w"), indent=1, default=str)
    log("done", REP["final"])


if __name__ == "__main__":
    main()
