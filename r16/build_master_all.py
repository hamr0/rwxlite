#!/usr/bin/env python3
"""Master list of every API operation collected for rounds 13, 15 and 16, one row per op_id, one status per row.
v2 (2026-11-21): reads the v2 dev/pick (pick_round16_v2.py), v2 rating, fills lang for every row, adds non_english; see docs PRD "Cleaning".
No labelling, no training, no server. Deterministic (no randomness; the r16 stage replay reuses the committed filter code).
Run (scratch venv has pandas/pyarrow):  nice -n 19 data/r16/scratch/venv/bin/python r16/build_master_all.py
Outputs: data/master/master-all.{parquet,csv.gz}, data/master/master-summary.md, data/master/master-report.json

STATUS PRECEDENCE (first match wins; exactly one status per row)
  r13 rows      : trained_r13 | r13_val (disjoint, asserted); the 5,716 v3eval rows are inside train: boolean r13_v3eval
  r15 rows      : trained_r15 > r15_holdout > dropped_val_overlap > r16_dev_old_unused > exam8_drop_rwxmap
                  > exam8_drop_name > rwxmap_flagged_r15 > dropped_<duplicate|no_text|junk|rpc|non_http|non_english>
                  > unused_clean | unused_other
  r16 rows      : replay of the r16/filter_github.py stages, first stage that removes the op names the status:
                  dropped_template, dropped_min5, dropped_duplicate (spec / op / cross_source), dropped_no_text, dropped_junk, dropped_rpc,
                  dropped_non_http, dropped_non_english, exam8_drop_name, dropped_known_vendor, dropped_near_dup, dropped_cap;
                  kept ops: exam8_drop_rwxmap > r16_dev > r16_pick_new > dropped_op_key_known (exact key = a
                  R13 train/val/v3eval or r15 master row) > dropped_op_key_dup (key duplicate inside the pick/dev or of a dev op; v2 pick) > unused_clean | unused_other
  unused_other  = passes every hard rule but carries a soft flag (huge_spec, odd_path, lorem, placeholder_text, autogen_opid_only, test_endpoint);
                  unused_clean = no soft flag.  Hard rules = the ones the r15/r16 filters applied (English, has text, not a duplicate, not a junk domain,
                  not RPC, HTTP method, not an exam #8 name hit).
  status_detail : the sub-reason (which new-vendor rule, which duplicate kind, ...).
  vendor_used   : the vendor_key has at least one row used (trained, holdout, val-overlap, dev, r16 pick, exam #8 drop, rwxmap flagged) or matches an
                  R13 seen token.  "never-used vendor" = vendor_used False.
"""
import collections, csv, gzip, hashlib, importlib.util, json, os, re, sys, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "r15"))
sys.path.insert(0, HERE)
import ids  # noqa: E402
import opkey  # noqa: E402


def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


M = load("r15master", os.path.join(REPO, "r15", "master.py"))
F = load("r15filter", os.path.join(REPO, "r15", "filter.py"))
P = load("r16pickdev", os.path.join(HERE, "pick_dev.py"))

D = os.path.join(REPO, "data")
OUT = os.path.join(D, "master")
RAW = os.path.join(D, "r16", "raw")
MASTER = os.path.join(D, "r15", "master", "ops-r15-master.parquet")
DROP = "/home/hamr/PycharmProjects/rwxmap/poc/exam8-r16-check/drop-list.csv"
DROP_SHA = "75d5fc7010aef75fa78fb20734fc4aa3cf40e9c0e231e83bb4301456e6ef9d3d"
SEED, CAP, MIN_OPS = "r16-cap-seed-16", 300, 5
SOFT = ["huge_spec", "odd_path", "lorem", "placeholder_text", "autogen_opid_only", "test_endpoint"]
t0 = time.time()
csv.field_size_limit(10 ** 9)


def log(*a):
    print("[%6.0fs]" % (time.time() - t0), *a, flush=True)


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def regdom_label(d):
    return d.split(".")[0] if d else ""


def soft_flag(fl):
    return fl.fillna("").str.contains("|".join(SOFT))


# =====================================================================================================  r16 replay
def r16_replay():
    """Replays r16/filter_github.py stage by stage; returns (per-raw-op table, stage counts, checks against collect-report-github.json)."""
    rep = json.load(open(os.path.join(D, "r16", "collect-report-github.json")))
    want = {s["stage"]: s["ops"] for s in rep["stages"]}
    light = [c for c in pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet")).schema.names if c not in ("summary", "description")]
    df = pd.read_parquet(os.path.join(RAW, "ops-raw.parquet"), columns=light)
    assert df["op_id"].is_unique
    df["_spec"] = df["repo"] + "\0" + df["file_path"] + "\0" + df["spec_sha256"]
    reason = pd.Series("", index=pd.Index(df["op_id"]), dtype=object)
    detail = pd.Series("", index=reason.index, dtype=object)
    lang = pd.Series("", index=reason.index, dtype=object)
    soft = pd.Series(False, index=reason.index)
    stage_counts = {}

    def chk(name, cur):
        stage_counts[name] = len(cur)
        assert len(cur) == want[name], (name, len(cur), want[name])

    def mark(before, after, status, why):
        gone = before.loc[~before["op_id"].isin(set(after["op_id"])), "op_id"]
        reason.loc[gone.to_numpy()] = status
        detail.loc[gone.to_numpy()] = why if isinstance(why, str) else ""
        return gone

    chk("ops_raw", df)
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
    log("r16 exam8 raw spec hits", len(hits_raw))

    tnorm = df["spec_title"].str.lower().str.strip()
    title_bad = tnorm.str.match(F.TEMPLATE_TITLE_RE) | tnorm.str.contains("petstore", regex=False)
    df["_pn"] = df["path"].map(ids.op_path_norm)
    g = df.assign(_t=df["_pn"].isin(F.TEMPLATE_PATHS)).groupby("_spec")["_t"].agg(["sum", "count"])
    pbs = set(g.index[(g["sum"] >= F.TEMPLATE_PATH_MIN_HITS) & (g["sum"] / g["count"] >= F.TEMPLATE_PATH_MIN_FRAC)])
    bad = title_bad | df["_spec"].isin(pbs)
    nxt = df[~bad]
    gone = mark(df, nxt, "dropped_template", "")
    detail.loc[df.loc[title_bad, "op_id"].to_numpy()] = "title"
    detail.loc[df.loc[~title_bad & bad, "op_id"].to_numpy()] = "paths_only"
    df = nxt; chk("after_template_petstore_drop", df)
    nxt = df[df.groupby("_spec")["op_id"].transform("count") >= MIN_OPS]
    mark(df, nxt, "dropped_min5", ""); df = nxt; chk("after_spec_min5_ops", df)
    df = df.sort_values(["stars", "repo", "file_path"], ascending=[False, True, True], kind="mergesort")
    first = df.drop_duplicates("spec_sha256")[["spec_sha256", "_spec"]].set_index("spec_sha256")["_spec"]
    nxt = df[df["_spec"] == df["spec_sha256"].map(first)]
    mark(df, nxt, "dropped_duplicate", "spec_same_sha256"); df = nxt; chk("after_spec_dedupe", df)
    nxt = df.drop_duplicates(["vendor_key", "method", "_pn"])
    mark(df, nxt, "dropped_duplicate", "op_same_vendor_method_path"); df = nxt; chk("after_op_dedupe", df)

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
    lang.loc[df["op_id"].to_numpy()] = df["lang"].to_numpy()
    soft.loc[df["op_id"].to_numpy()] = soft_flag(df["flags"]).to_numpy()
    df_e = df
    log("r16 text/lang/flags done")

    q = df[df["has_text"]]; mark(df, q, "dropped_no_text", ""); chk("after_has_text", q)
    q2 = q[~q["flags"].str.contains("junk_domain")]; mark(q, q2, "dropped_junk", "junk_domain"); q = q2; chk("after_junk_domain_flag", q)
    q2 = q[~q["flags"].str.contains("non_http_method")]; mark(q, q2, "dropped_non_http", ""); q = q2; chk("after_non_http_method", q)
    q2 = q[~q["flags"].str.contains(r"(?:^|;)rpc(?:;|$)")]; mark(q, q2, "dropped_rpc", ""); q = q2; chk("after_rpc_flag", q)
    q2 = q[q["lang"] == "en"]; mark(q, q2, "dropped_non_english", ""); q = q2; chk("after_lang_en", q)

    mcols = ["op_id", "vendor_id", "vendor_key", "vendor_kind", "spec_sha256", "method", "path", "operationId", "summary", "servers_domains",
             "contact_domain", "logo_domain", "method_norm", "path_norm", "spec_title", "title_norm", "repo", "repo_owner", "repo_name",
             "servers", "contact_url", "file_path"]
    mast = pd.read_parquet(MASTER, columns=mcols)
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
    dev_sha = set()
    with gzip.open(os.path.join(D, "r16", "dev", "dev-ops.csv.gz"), "rt", newline="") as f:
        for r in csv.DictReader(f):
            dev_sha.add(r["spec_sha256"])
    ex7 = F.load_exam7()

    comb = pd.concat([df_e[["spec_sha256", "method_norm", "path_norm"]], mast[["spec_sha256", "method_norm", "path_norm"]]], ignore_index=True)
    sg = M.spec_groups(comb)
    del comb
    ex8_master_sha = set()
    ms = mast.drop_duplicates("spec_sha256")
    for r in ms.to_dict("records"):
        r["repo_url"] = "https://github.com/" + r["repo"] if r["repo"] else ""
        w, s = P.hits8(r)
        if w or s:
            ex8_master_sha.add(r["spec_sha256"])
    ex8_groups = {sg[s] for s in (ex8_sha | ex8_master_sha) if s in sg}
    m_groups = {sg[s] for s in m_shas if s in sg}

    q = q.copy()
    q["_ex8_own"] = q["_spec"].map(lambda s: s in hits_raw)
    q["_ex8_sha"] = q["spec_sha256"].isin(ex8_sha) & ~q["_ex8_own"]
    q["_ex8_grp"] = q["spec_sha256"].map(lambda s: sg.get(s, -1) in ex8_groups) & ~q["_ex8_own"] & ~q["_ex8_sha"]
    hit8 = q["_ex8_own"] | q["_ex8_sha"] | q["_ex8_grp"]
    nxt = q[~hit8]
    mark(q, nxt, "exam8_drop_name", "")
    detail.loc[q.loc[q["_ex8_own"], "op_id"].to_numpy()] = "own_hit"
    detail.loc[q.loc[q["_ex8_sha"], "op_id"].to_numpy()] = "same_sha256_mirror"
    detail.loc[q.loc[q["_ex8_grp"], "op_id"].to_numpy()] = "near_duplicate_of_exam8_spec"
    q = nxt; chk("after_exam8_freeze", q)

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
            "r13_token": bool(labs & r13),
            "r15_exclusion_key": bool(ident & exkeys),
            "exam7_list": bool(F.exam7_hits(type("R", (), s)(), ex7)),
            "rwxmap_flagged": s["spec_sha256"] in flagged,
            "dev_pick": s["vendor_key"] in dev_v or s["spec_sha256"] in dev_sha,
            "near_dup_of_master_spec": sg.get(s["spec_sha256"], -1) in m_groups,
        }
    fl = pd.DataFrame.from_dict(flag, orient="index")
    q = q.copy()
    for c in fl.columns:
        q["_f_" + c] = q["_spec"].map(fl[c]).fillna(False).astype(bool)
    order = [("sha_in_master", "after_nv_spec_sha_in_master"), ("vendor_in_master", "after_nv_vendor_key_in_master"),
             ("domain_in_master", "after_nv_registrable_domain_in_master"), ("r13_token", "after_nv_r13_token"),
             ("r15_exclusion_key", "after_nv_r15_exclusion_keys"), ("exam7_list", "after_nv_exam7_list"),
             ("rwxmap_flagged", "after_nv_rwxmap_flagged"), ("dev_pick", "after_nv_r16_dev_pick"),
             ("near_dup_of_master_spec", "after_nv_near_dup_of_master_spec")]
    for c, name in order:
        nxt = q[~q["_f_" + c]]
        mark(q, nxt, "dropped_known_vendor", c); q = nxt; chk(name, q)

    # cross-source duplicate rule: the committed collection run (collect-report-github.json) dropped 0 ops here because its hash-based key was broken
    # (PRD "Cleaning"; fixed in r16/filter_github.py, not re-run), so this replay drops 0 too and the stage counts keep matching the report. The ops that
    # the fixed rule matches (exact key = r16/opkey.py k1 against the r15 master) are flagged; the v2 pick/dev and the status dropped_op_key_known apply it.
    k_m = set(opkey.k1(mast))
    xd_ids = {o for o, kk in zip(q["op_id"], opkey.k1(q)) if kk in k_m}
    log("cross-source key matches (exact key vs r15 master; not dropped in the committed collection run)", len(xd_ids))
    chk("after_nv_cross_source_duplicate_ops", q)

    stats = q.groupby("spec_sha256").agg(tl=("text_clean", lambda s: int(s.str.len().sum())))
    grp = {s: sg[s] for s in stats.index if s in sg}
    sdf = pd.DataFrame({"sha": list(grp), "g": list(grp.values())})
    sdf["tl"] = sdf["sha"].map(stats["tl"])
    sdf = sdf.sort_values(["g", "tl", "sha"], ascending=[True, False, True])
    primary = sdf.groupby("g")["sha"].first().to_dict()
    nd = q["spec_sha256"].map(lambda s: s in grp and primary[grp[s]] != s)
    nxt = q[~nd]; mark(q, nxt, "dropped_near_dup", "inner_near_duplicate_spec"); q = nxt; chk("after_inner_near_duplicate_specs", q)
    q = q.copy()
    q["_h"] = [hashlib.sha256((SEED + o).encode()).hexdigest() for o in q["op_id"]]
    nxt = q.sort_values(["vendor_key", "_h"]).groupby("vendor_key", sort=False).head(CAP)
    mark(q, nxt, "dropped_cap", "300_per_vendor"); q = nxt; chk("after_cap_300_per_vendor", q)
    reason.loc[q["op_id"].to_numpy()] = "kept"
    assert (reason != "").all()

    # per-op output table (every raw op once)
    raw_cols = ["op_id", "method", "path", "operationId", "vendor_key", "licence", "spec_sha256", "repo", "title_norm", "servers_domains"]
    raw = pd.read_parquet(os.path.join(RAW, "ops-raw.parquet"), columns=raw_cols + ["summary"])
    raw["summary"] = raw["summary"].fillna("").str.slice(0, 200)
    raw["vendor_kind"] = np.where(raw["vendor_key"].str.startswith("title:"), "title", np.where(raw["vendor_key"].str.startswith("owner:"), "owner", "domain"))
    raw["status0"] = reason.reindex(raw["op_id"]).to_numpy()
    raw["status_detail"] = detail.reindex(raw["op_id"]).to_numpy()
    raw["lang"] = lang.reindex(raw["op_id"]).to_numpy()
    raw["soft_flag"] = soft.reindex(raw["op_id"]).to_numpy()
    raw["key_in_r15_master"] = raw["op_id"].isin(xd_ids).to_numpy()
    return raw, stage_counts, int(len(hits_raw))


# =====================================================================================================  main
def main():
    os.makedirs(OUT, exist_ok=True)
    R = {"script": "r16/build_master_all.py"}

    # ---------------- inputs
    assert sha_file(DROP) == DROP_SHA
    dl = pd.read_csv(DROP)
    assert len(dl) == 260 and int(dl["ops"].sum()) == 4680
    drop_sha = set(dl["spec_sha256"])
    tr15 = pd.read_parquet(os.path.join(D, "round15", "train.parquet"), columns=["id", "src", "provider", "vendor", "method", "path", "operationId", "summary"])
    t13 = pd.read_parquet(os.path.join(D, "round13", "train.parquet"), columns=["id", "provider", "vendor", "method", "path", "operationId", "summary"])
    v13 = pd.read_parquet(os.path.join(D, "round13", "val.parquet"), columns=["id", "provider", "vendor", "method", "path", "operationId", "summary"])
    e13 = pd.read_parquet(os.path.join(D, "round13", "v3eval.parquet"), columns=["id", "provider", "vendor", "method", "path", "operationId", "summary"])
    prov = pd.read_csv(os.path.join(D, "round13", "provenance.csv")).drop_duplicates("id").set_index("id")["source"]
    assert len(t13) == 102668 and len(v13) == 4180 and len(e13) == 5716
    assert not (set(t13.id) & set(v13.id)) and not (set(v13.id) & set(e13.id))
    assert set(e13.id) <= set(t13.id)  # v3eval rows are all inside R13 train (re-scored subset): flagged, not a second row
    assert set(tr15.loc[tr15.src == "r13", "id"]) == set(t13.id) and (tr15.src == "r15").sum() == 199543

    # ---------------- r13 rows
    def r13_rows(d, status):
        o = pd.DataFrame({"op_id": d["id"], "source_round": "r13", "source": d["id"].map(prov).fillna("r13-corpus"),
                          "vendor_key": d["provider"].fillna(""), "vendor_kind": "r13_provider", "method": d["method"], "path": d["path"],
                          "operationId": d["operationId"].fillna(""), "summary": d["summary"].fillna("").str.slice(0, 200), "lang": "", "licence": "",
                          "spec_sha256": "", "origin": "", "status": status, "status_detail": "", "soft_flag": False, "title_norm": "", "servers_domains": ""})
        return o
    r13_all = pd.concat([r13_rows(t13, "trained_r13"), r13_rows(v13, "r13_val")], ignore_index=True)

    # ---------------- r15 rows
    m = pd.read_parquet(MASTER)
    assert len(m) == 802196 and m["op_id"].is_unique
    pick = pd.read_csv(os.path.join(D, "r15", "picks", "pick-200000-1.csv.gz"), usecols=["op_id"])["op_id"]
    assert len(pick) == 200000 and pick.is_unique and pick.isin(m["op_id"]).all()
    trained15 = set(tr15.loc[tr15.src == "r15", "id"])
    hold = set(pd.read_csv(os.path.join(D, "r15", "labels", "disagree-sample-400.csv"), usecols=["op_id"])["op_id"])
    assert len(hold) == 400 and trained15 <= set(pick) and not (hold & trained15) and hold <= set(pick)
    valov = set(pick) - trained15 - hold
    assert len(valov) == 57, len(valov)
    dev_old = pd.read_csv(os.path.join(D, "r16", "dev", "dev-ops.csv.gz"), usecols=["op_id"])["op_id"]
    assert dev_old.isin(m["op_id"]).all() and len(dev_old) == 4039
    dev_old = set(dev_old)
    ex8_master_sha = set()
    for r in m.drop_duplicates("spec_sha256")[["spec_sha256", "vendor_key", "servers", "servers_domains", "contact_domain", "logo_domain", "contact_url", "spec_title",
                                                         "title_norm", "repo", "repo_owner", "repo_name", "file_path"]].to_dict("records"):
        r["repo_url"] = "https://github.com/" + r["repo"] if r["repo"] else ""
        w, s = P.hits8(r)
        if w or s:
            ex8_master_sha.add(r["spec_sha256"])
    fl = m["flags"].fillna("")
    dup = m["dup_of"].fillna("") != ""
    st = np.select([m["op_id"].isin(trained15), m["op_id"].isin(hold), m["op_id"].isin(valov), m["op_id"].isin(dev_old),
                    m["spec_sha256"].isin(drop_sha), m["spec_sha256"].isin(ex8_master_sha),
                    dup, ~m["has_text"].astype(bool), fl.str.contains("junk_domain"), fl.str.contains(r"(?:^|;)rpc(?:;|$)"),
                    fl.str.contains("non_http_method"), m["lang"] != "en"],
                   ["trained_r15", "r15_holdout", "dropped_val_overlap", "r16_dev_old_unused", "exam8_drop_rwxmap", "exam8_drop_name",
                    "dropped_duplicate", "dropped_no_text", "dropped_junk", "dropped_rpc", "dropped_non_http", "dropped_non_english"],
                   default="unused")
    m["status"] = st
    m.loc[m["status"] == "unused", "status"] = np.where(soft_flag(fl[m["status"] == "unused"]), "unused_other", "unused_clean")
    m15 = pd.DataFrame({"op_id": m["op_id"], "source_round": "r15", "source": m["source"], "vendor_key": m["vendor_key"], "vendor_kind": m["vendor_kind"],
                        "method": m["method"], "path": m["path"], "operationId": m["operationId"], "summary": m["summary"].fillna("").str.slice(0, 200),
                        "lang": m["lang"], "licence": m["licence"], "spec_sha256": m["spec_sha256"], "origin": m["repo"], "status": m["status"],
                        "status_detail": "", "soft_flag": soft_flag(fl).to_numpy(), "title_norm": m["title_norm"], "servers_domains": m["servers_domains"]})
    m15.loc[m15["status"] == "dropped_duplicate", "status_detail"] = "near_duplicate_spec_dup_of"
    # rows rwxmap flagged (removed from the master at build time) and rows removed as cross-source duplicates (still in the r15 input files)
    dr = pd.read_csv(os.path.join(D, "r15", "master", "dropped-rwxmap.csv.gz"), dtype=str, keep_default_na=False)
    assert len(dr) == 4963 and dr["op_id"].is_unique and not dr["op_id"].isin(m["op_id"]).any()
    dr15 = pd.DataFrame({"op_id": dr["op_id"], "source_round": "r15", "source": dr["source"], "vendor_key": dr["vendor_key"], "vendor_kind": "",
                         "method": dr["method"], "path": dr["path"], "operationId": dr["operationId"], "summary": dr["summary"].str.slice(0, 200), "lang": "",
                         "licence": dr["licence"], "spec_sha256": dr["spec_sha256"], "origin": dr["repo"], "status": "rwxmap_flagged_r15",
                         "status_detail": "spec on rwxmap flagged list (319 specs)", "soft_flag": False, "title_norm": dr["title_norm"], "servers_domains": dr["servers_domains"]})
    ins = []
    for f in ["ops-r15", "ops-r15-swaggerhub", "ops-r15-catalogues", "ops-r15-cloud"]:
        d = pd.read_parquet(os.path.join(D, "r15", f + ".parquet"))
        d["_file"] = f
        ins.append(d)
    ins = pd.concat(ins, ignore_index=True)
    nin = len(ins)
    assert ins["op_id"].is_unique
    exact_dups = 0
    xs = ins[~ins["op_id"].isin(m["op_id"]) & ~ins["op_id"].isin(dr["op_id"])]
    xs15 = pd.DataFrame({"op_id": xs["op_id"], "source_round": "r15", "source": xs["source"].where(xs["source"].notna(), "github"), "vendor_key": xs["vendor_key"],
                         "vendor_kind": "", "method": xs["method"], "path": xs["path"], "operationId": xs["operationId"],
                         "summary": xs["summary"].fillna("").str.slice(0, 200), "lang": "", "licence": xs["licence"], "spec_sha256": xs["spec_sha256"],
                         "origin": xs["repo"], "status": "dropped_duplicate", "status_detail": "r15 master dedupe (8,789 cross-source + 23 exact duplicates; not separable per row)",
                         "soft_flag": False, "title_norm": xs["title_norm"], "servers_domains": xs["servers_domains"]})
    R["r15_input_rows"] = nin; R["r15_exact_duplicate_rows_same_op_id_count_only"] = 23
    assert len(xs15) == 8789 + 23, len(xs15)
    assert len(m) + len(dr15) + len(xs15) == nin
    r15_all = pd.concat([m15, dr15, xs15], ignore_index=True)
    log("r13/r15 rows", len(r13_all), len(r15_all))

    # ---------------- r16 rows
    cache = os.path.join(D, "r16", "scratch", "r16-replay-cache")
    if "--use-cache" in sys.argv and os.path.exists(cache + ".parquet"):  # dev convenience only; the default run replays from data/r16/raw
        raw = pd.read_parquet(cache + ".parquet"); cj = json.load(open(cache + ".json")); stage_counts, n_hit8 = cj["stage_counts"], cj["n_hit8"]
    else:
        raw, stage_counts, n_hit8 = r16_replay()
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        raw.to_parquet(cache + ".parquet", index=False); json.dump({"stage_counts": stage_counts, "n_hit8": n_hit8}, open(cache + ".json", "w"))
    pool = pd.read_parquet(os.path.join(D, "r16", "ops-r16-github.parquet"), columns=["op_id", "method", "path", "operationId", "summary"])
    kept_ids = pool["op_id"]
    assert len(kept_ids) == 807949 and set(kept_ids) == set(raw.loc[raw.status0 == "kept", "op_id"])
    new = pd.read_csv(os.path.join(D, "r16", "pick", "new-300k-v2.csv.gz"), usecols=["op_id"])["op_id"]
    devn = pd.read_csv(os.path.join(D, "r16", "dev-en", "dev-ops-v2.csv.gz"), usecols=["op_id"])["op_id"]
    pr2 = json.load(open(os.path.join(D, "r16", "pick", "pick-report-v2.json")))
    N_DEV = pr2["dev_v2"]["ops"]
    assert len(new) == 300000 and len(devn) == N_DEV and new.is_unique and devn.is_unique
    new, devn = set(new), set(devn)
    # exact-key copies of rows we trained on or hold out (r13 train/val/v3eval, r15 master incl. trained and holdout): r16/opkey.py
    S1, _S2 = opkey.known_sets(opkey.load_known(D))
    pool["k1"] = opkey.k1(pool)
    pool["src1"] = opkey.first_source(pool["k1"], S1)
    A_known = pool.set_index("op_id")["src1"]
    allk = set().union(*S1.values())
    pk = pool[pool["op_id"].isin(new | devn)]
    assert not any(k in allk for k in pk["k1"]), "pick/dev op shares its exact key with a trained/holdout row"
    assert not pk.loc[pk["op_id"].isin(new), "k1"].duplicated().any(), "exact-key duplicate inside the pick"
    assert not pk.loc[pk["op_id"].isin(devn), "k1"].duplicated().any(), "exact-key duplicate inside dev"
    assert not set(pk.loc[pk["op_id"].isin(new), "k1"]) & set(pk.loc[pk["op_id"].isin(devn), "k1"]), "pick op shares its exact key with a dev op"
    dv2 = pd.read_csv(os.path.join(D, "r16", "pick", "dropped-v2.csv.gz"), dtype=str, keep_default_na=False)
    dup_ids = set(dv2.loc[dv2["reason"].isin(["dup_in_dev", "dup_of_dev", "dup_in_pick"]), "op_id"])
    del pool, pk
    assert new <= set(kept_ids) and devn <= set(kept_ids) and not (new & devn)
    ex8r = raw["spec_sha256"].isin(drop_sha) & (raw["status0"] == "kept")
    assert int(ex8r.sum()) == 4680
    assert not (new & set(raw.loc[ex8r, "op_id"])) and not (devn & set(raw.loc[ex8r, "op_id"]))
    softk = raw["soft_flag"]
    known_src = raw["op_id"].map(A_known).fillna("")
    s16 = np.select([raw["status0"] != "kept", ex8r, raw["op_id"].isin(devn), raw["op_id"].isin(new), known_src != "", raw["op_id"].isin(dup_ids), softk],
                    [raw["status0"], "exam8_drop_rwxmap", "r16_dev", "r16_pick_new", "dropped_op_key_known", "dropped_op_key_dup", "unused_other"], default="unused_clean")
    detail_k = np.where((raw["status0"] == "kept") & ~ex8r & ~raw["op_id"].isin(devn) & ~raw["op_id"].isin(new) & (known_src != ""), "exact key = a " + known_src + " row", "")
    raw["status_detail"] = np.where(detail_k != "", detail_k, raw["status_detail"].to_numpy())
    r16_all = pd.DataFrame({"op_id": raw["op_id"], "source_round": "r16", "source": "github", "vendor_key": raw["vendor_key"], "vendor_kind": raw["vendor_kind"],
                            "method": raw["method"], "path": raw["path"], "operationId": raw["operationId"], "summary": raw["summary"], "lang": raw["lang"],
                            "licence": raw["licence"], "spec_sha256": raw["spec_sha256"], "origin": raw["repo"], "status": s16,
                            "status_detail": raw["status_detail"].to_numpy(), "soft_flag": raw["soft_flag"], "title_norm": raw["title_norm"], "key_in_r15_master": raw["key_in_r15_master"].to_numpy(),
                            "servers_domains": raw["servers_domains"]})
    del raw

    # ---------------- combine
    A = pd.concat([r13_all, r15_all, r16_all], ignore_index=True)
    assert A["op_id"].is_unique, "op_id collision across sources"
    A["method"] = A["method"].fillna("").str.upper()
    for c in ["vendor_key", "operationId", "licence", "spec_sha256", "lang", "origin", "status_detail"]:
        A[c] = A[c].fillna("")

    # ---------------- language: every row gets one (nothing is deleted; non-English rows keep their status)
    # Same detector as the collections (r15/master.py lang_signal) on the text that exists: summary + description (r16 raw ops), else summary, else operationId, else 'unknown'.
    # Rows that already carry a collection-time lang keep it (that one also uses the spec-majority smoothing for weak English evidence).
    A["lang_computed_here"] = A["lang"].fillna("") == ""
    blank16 = set(A.loc[A["lang_computed_here"] & (A["source_round"] == "r16"), "op_id"])
    t16 = {}
    for b in pq.ParquetFile(os.path.join(RAW, "ops-raw.parquet")).iter_batches(batch_size=50000, columns=["op_id", "summary", "description"]):
        t = b.to_pandas()
        t = t[t["op_id"].isin(blank16)]
        for o, su, de in zip(t["op_id"], t["summary"], t["description"]):
            t16[o] = M.make_text(su, de)
    bl = A[A["lang_computed_here"]]
    texts = [t16.get(o) or su or oi for o, su, oi in zip(bl["op_id"], bl["summary"].fillna(""), bl["operationId"].fillna(""))]
    sig = [M.lang_signal(t) for t in texts]
    A.loc[bl.index, "lang"] = [(l[0] if l[0] else "unknown") for l in sig]
    assert (A["lang"].fillna("") != "").all()
    A["non_english"] = A["lang"].isin(["zh", "ru", "other"])
    log("lang filled for", int(A["lang_computed_here"].sum()), "rows; non-English", int(A["non_english"].sum()))

    # ---------------- flags
    rep_ids = pd.read_csv(os.path.join(D, "r16", "pick", "old-replay-ids.csv"))
    assert len(rep_ids) == 60000 and rep_ids["id"].is_unique
    A["key_in_r15_master"] = A["key_in_r15_master"].fillna(False).astype(bool)
    A["r13_v3eval"] = A["op_id"].isin(set(e13.id))
    assert int(A["r13_v3eval"].sum()) == 5716
    A["r16_old_replay"] = A["op_id"].isin(set(rep_ids["id"]))
    assert int(A["r16_old_replay"].sum()) == 60000
    assert set(A.loc[A["r16_old_replay"], "status"]) <= {"trained_r13", "trained_r15"}
    conf = set(pd.read_csv(os.path.join(D, "r16", "review", "confident.csv.gz"), usecols=["id"])["id"])
    A["confident_disagreement"] = A["op_id"].isin(conf)
    assert int(A["confident_disagreement"].sum()) == 755 == len(conf)
    bge = pd.read_parquet(os.path.join(D, "r16", "pick", "bge-rating-v2.parquet"), columns=["op_id", "opus", "part"])
    assert len(bge) == 304475
    opus_ids = set(bge.loc[bge["opus"] & (bge["part"] != "dev"), "op_id"])
    A["opus_candidate"] = A["op_id"].isin(opus_ids)
    rs = json.load(open(os.path.join(D, "r16", "pick", "rating-summary-v2.json")))
    assert int(A["opus_candidate"].sum()) == rs["opus_union_new"], (int(A["opus_candidate"].sum()), rs["opus_union_new"])
    assert set(A.loc[A["opus_candidate"], "status"]) == {"r16_pick_new"}

    # ---------------- vendor_used (never-used vendor test)
    used_st = {"trained_r13", "r13_val", "trained_r15", "r15_holdout", "dropped_val_overlap", "r16_dev_old_unused", "r16_pick_new", "r16_dev",
               "exam8_drop_rwxmap", "exam8_drop_name", "rwxmap_flagged_r15"}
    used_v = set(A.loc[A["status"].isin(used_st) & (A["vendor_key"] != ""), "vendor_key"])
    r13tok = {l.strip() for l in open(os.path.join(D, "round13", "vendors-r13-seen.txt")) if l.strip()}
    combo = A.loc[A["source_round"] != "r13", ["vendor_key", "vendor_kind", "title_norm", "servers_domains"]].drop_duplicates()
    r13_hit = set()
    for r in combo.itertuples(index=False):
        labs = set()
        if r.vendor_kind == "domain" or "." in r.vendor_key:
            labs.add(regdom_label(r.vendor_key))
        if r.vendor_kind == "title":
            labs.add(r.title_norm)
        labs |= {regdom_label(d) for d in r.servers_domains.split("|") if d}
        if labs & r13tok or r.vendor_key in r13tok:
            r13_hit.add(r.vendor_key)
    reserved_st = {"r13_val", "r15_holdout", "r16_dev", "r16_dev_old_unused", "exam8_drop_rwxmap", "exam8_drop_name", "rwxmap_flagged_r15"}
    trained_st = {"trained_r13", "trained_r15", "dropped_val_overlap"}
    v_res = set(A.loc[A["status"].isin(reserved_st), "vendor_key"]) | r13_hit
    v_tr = set(A.loc[A["status"].isin(trained_st), "vendor_key"])
    v_pick = set(A.loc[A["status"] == "r16_pick_new", "vendor_key"])
    A["vendor_class"] = np.select([A["vendor_key"].isin(v_res), A["vendor_key"].isin(v_tr), A["vendor_key"].isin(v_pick)],
                                  ["reserved_dev_exam", "trained_r13_r15", "r16_pick_only"], default="never_used")
    A.loc[A["vendor_key"] == "", "vendor_class"] = ""
    A["vendor_used"] = A["vendor_class"] != "never_used"
    A["vendor_key_used_by_rule"] = np.where(A["vendor_key"].isin(r13_hit) & ~A["vendor_key"].isin(used_v), "r13_token", "")

    # ---------------- asserts
    tr_st = {"trained_r13", "trained_r15"}
    assert not (set(A.loc[A["status"].isin(tr_st), "spec_sha256"]) & drop_sha - {""}), "training row on rwxmap exam8 drop list spec"
    assert not set(A.loc[A["status"].isin(tr_st), "op_id"]) & set(A.loc[A["status"].isin({"r16_dev", "exam8_drop_rwxmap", "exam8_drop_name", "r16_dev_old_unused"}), "op_id"])
    assert (A["status"] == "trained_r13").sum() == 102668 and (A["status"] == "trained_r15").sum() == 199543
    assert (A["status"] == "r15_holdout").sum() == 400 and (A["status"] == "dropped_val_overlap").sum() == 57
    assert (A["status"] == "r16_dev").sum() == N_DEV and (A["status"] == "r16_pick_new").sum() == 300000 and (A["status"] == "exam8_drop_rwxmap").sum() == 4680
    assert (A["status"] == "rwxmap_flagged_r15").sum() == 4963 and (A["status"] == "r16_dev_old_unused").sum() == 4039
    assert ((A["source_round"] == "r15").sum()) == 802196 + 4963 + 8812
    assert ((A["source_round"] == "r16").sum()) == 1773972
    kept16 = A[(A["source_round"] == "r16") & A["status"].isin(["r16_pick_new", "r16_dev", "exam8_drop_rwxmap", "unused_clean", "unused_other", "dropped_op_key_known", "dropped_op_key_dup"])]
    assert len(kept16) == 807949
    assert A["status"].notna().all()
    ex8_train = A[A["status"].isin(tr_st) & A["spec_sha256"].isin(ex8_master_sha)]
    R["trained_rows_on_exam8_name_hit_master_specs"] = int(len(ex8_train))
    # no pick/dev op shares the exact key with a trained/holdout row, none duplicated inside the pick or dev or between them: asserted in the r16 stage above
    # (before the status assignment); here: the statuses must agree with it
    assert not (A["status"].isin(["r16_pick_new", "r16_dev"]) & A["status_detail"].str.startswith("exact key =")).any()
    assert not (A.loc[A["status"].isin(["unused_clean", "unused_other"]) & (A["source_round"] == "r16"), "status_detail"].str.startswith("exact key =")).any()
    log("asserts passed", len(A))

    # ---------------- write
    cols = ["op_id", "source_round", "source", "vendor_key", "vendor_kind", "method", "path", "operationId", "summary", "lang", "licence", "spec_sha256",
            "origin", "status", "status_detail", "lang_computed_here", "non_english", "key_in_r15_master", "r13_v3eval", "r16_old_replay", "confident_disagreement", "opus_candidate", "soft_flag", "vendor_used", "vendor_class", "vendor_key_used_by_rule"]
    A = A[cols].sort_values("op_id").reset_index(drop=True)
    A.to_parquet(os.path.join(OUT, "master-all.parquet"), index=False)
    A.to_csv(os.path.join(OUT, "master-all.csv.gz"), index=False, compression={"method": "gzip", "mtime": 0})

    # ---------------- summary
    tab = pd.crosstab(A["status"], A["source_round"], margins=True, margins_name="total")
    ue = A[(A["status"] == "unused_clean") & (A["lang"] == "en")]
    avail = ue[~ue["vendor_used"]]  # strict: never-used vendor
    cls = ue.groupby("vendor_class").agg(ops=("op_id", "size"), vendors=("vendor_key", "nunique"))
    cls = cls.fillna(0).astype(int)
    byr = ue.groupby(["source_round", "vendor_class"]).agg(ops=("op_id", "size"), vendors=("vendor_key", "nunique")).reset_index()
    R["counts_status_by_round"] = {k: {c: int(v) for c, v in r.items()} for k, r in tab.iterrows()}
    R["headline"] = {"strict_never_used_vendor_ops": int(len(avail)), "strict_never_used_vendor_vendors": int(avail["vendor_key"].nunique()),
                     "unused_clean_en_ops": int(len(ue)), "unused_clean_en_vendors": int(ue["vendor_key"].nunique()),
                     "by_vendor_class": cls.to_dict("index"), "by_round_and_class": byr.to_dict("records"),
                     "unused_other_en_ops": int(((A["status"] == "unused_other") & (A["lang"] == "en")).sum())}
    R["r16_stage_counts_match_report"] = stage_counts
    R["r16_exam8_raw_spec_hits"] = n_hit8
    R["master_sha256"] = sha_file(os.path.join(OUT, "master-all.parquet"))
    json.dump(R, open(os.path.join(OUT, "master-report.json"), "w"), indent=1, default=str)
    lang_tab = pd.crosstab(A["lang"], A["source_round"], margins=True, margins_name="total")

    def md(t):
        t = t.reset_index()
        h = "| " + " | ".join(str(c) for c in t.columns) + " |\n|" + "---|" * len(t.columns) + "\n"
        return h + "\n".join("| " + " | ".join(f"{v:,}" if isinstance(v, (int, np.integer)) else str(v) for v in r) + " |" for r in t.itertuples(index=False)) + "\n"
    ne = A[A["non_english"]]
    ne_tab = ne.groupby(["lang", "source_round", "status"]).size().rename("ops").reset_index().set_index(["lang", "source_round", "status"])
    ne_clean = ne[ne["status"] == "dropped_non_english"]
    ne_clean_tab = pd.crosstab(ne_clean["lang"], ne_clean["source_round"], margins=True, margins_name="total")
    R["non_english"] = {"total": int(len(ne)), "unknown_lang": int((A["lang"] == "unknown").sum()), "otherwise_clean": int(len(ne_clean)),
                        "otherwise_clean_vendors": int(ne_clean["vendor_key"].nunique()),
                        "by_lang_round_status": {"|".join(k): int(v) for k, v in ne.groupby(["lang", "source_round", "status"]).size().items()},
                        "lang_computed_here": int(A["lang_computed_here"].sum())}
    json.dump(R, open(os.path.join(OUT, "master-report.json"), "w"), indent=1, default=str)
    dt = A[A["status_detail"] != ""].groupby(["status", "status_detail"]).size().rename("ops").reset_index()
    L = ["# Master list: every op collected for rounds 13, 15 and 16\n",
         f"Built by `r16/build_master_all.py` (deterministic). File: `data/master/master-all.parquet` ({len(A):,} rows, sha256 `{R['master_sha256']}`) and `.csv.gz`.\n",
         "One row per `op_id`; exactly one `status` per row (precedence in the script docstring and in `docs/product/prd-r16-vendor-data.md`, Master list).\n",
         "## Headline\n",
         f"**Clean English rows from never-used vendors still available after round 16: {len(avail):,} ops from {avail['vendor_key'].nunique():,} vendors** "
         "(vendors whose every pick row was removed as a key copy in v2, so they are not used any more). Apart from them every vendor that has clean unused rows already has at least one row used somewhere: "
         "r15 and r16 both drew from every eligible vendor (water-filling, small vendors whole), so no vendor is wholly untouched. The honest available pool is therefore the unused rows of already-touched vendors:\n",
         f"**Unused clean English rows (any vendor class): {len(ue):,} ops from {ue['vendor_key'].nunique():,} vendors** (r16 rows whose exact key equals a trained/holdout row are status `dropped_op_key_known`, not counted here; r15 unused rows were not key-checked against trained rows).\n",
         md(cls),
         "Vendor classes (precedence): `reserved_dev_exam` = vendor has a row in val, holdout, dev (r16 or earlier unused dev), exam #8 drop, or rwxmap flagged list, or matches an R13 seen token; "
         "`trained_r13_r15` = vendor has a trained or val-overlap row; `r16_pick_only` = vendor's only used rows are the r16 new pick (not yet trained: the nearest thing to a new vendor for round 17); `never_used` = none of those.\n",
         "Definition of a row: status `unused_clean` = passes every hard rule the r15/r16 filters applied (English, has text, not a duplicate, not a junk domain, not RPC, HTTP method, not an exam #8 name hit, not on the rwxmap drop list) and has no soft flag "
         f"(huge_spec / odd_path / lorem / placeholder_text / autogen_opid_only / test_endpoint). Soft-flagged unused rows (`unused_other`, English): {int(((A['status']=='unused_other') & (A['lang']=='en')).sum()):,}.\n",
         "By source round and class:\n", md(byr.set_index(["source_round", "vendor_class"])),
         "## Status by source round\n", md(tab),
         "## Language by source round\n", "Every row has a lang (see the non-English section for how the blanks of the earlier build were filled).\n", md(lang_tab),
         "## Non-English rows (kept, never deleted)\n",
         "`lang` is filled for every row; `non_english` = lang in zh, ru, other. Rows keep their status (for example `dropped_non_english`). `lang_computed_here` marks rows tagged in this build "
         "(r13 rows, r16 ops dropped before the text stage, r15 input-only rows) with the same detector (r15/master.py `lang_signal`) on summary+description, else summary, else operationId, else `unknown` "
         "(no letters). Collection-time tags (spec-majority smoothed) were kept as they were.\n",
         f"Non-English rows in total: **{int(A['non_english'].sum()):,}**; `unknown` (no text): {int((A['lang']=='unknown').sum()):,}.\n",
         "By lang x source round x status:\n", md(ne_tab),
         f"**Non-English rows that are otherwise clean** (status `dropped_non_english`: has text, not a duplicate, not a junk domain, not RPC, HTTP method; the pool a person might look at some day): **{int(len(ne_clean)):,}** ops from {ne_clean['vendor_key'].nunique():,} vendors. By lang x round:\n",
         md(ne_clean_tab),
         "Non-English rows dropped for another reason first (template, fewer than 5 ops, duplicate, no text, junk, ...) are in the first table under their own status and are not counted as clean.\n",
         "## Status detail\n", md(dt.set_index("status")),
         "## Reconciliation\n",
         "- r13: 102,668 train + 4,180 val; the 5,716 v3eval rows are inside train (column `r13_v3eval`).\n- r15: 802,196 master + 4,963 rwxmap-dropped + 8,812 master-dedupe removals (8,789 cross-source + 23 exact duplicates; the per-row split is not stored) = 815,971 = the four r15 input files.",
         "- r16: 1,773,972 raw ops, each assigned the stage that removed it; every stage count equals `collect-report-github.json` (asserted); kept 807,949 = 4,680 exam8_drop_rwxmap + 4,475 r16_dev + 300,000 r16_pick_new + unused.",
         "- Count-only stages: r15 raw-collection stages before the input files (template, min 5 ops, spec/op dedupe, cap; r15 raw data was deleted 2026-11-19) are in `data/r15/collect-report*.json`, not per row.",
         f"- Cleaning (2026-11-21): the cross-source duplicate rule of `r16/filter_github.py` dropped 0 ops in the committed collection run (broken hash key, see PRD Cleaning); {int(A['key_in_r15_master'].sum()):,} r16 ops that reached that stage have the same exact key as an r15 master row (column `key_in_r15_master`). The v2 pick/dev applies the fixed rule: r16 rows whose exact key equals a row of R13 train/val/v3eval or the r15 master get status `dropped_op_key_known` ({int((A['status']=='dropped_op_key_known').sum()):,}), rows removed as key duplicates inside the pick/dev or against dev get `dropped_op_key_dup` ({int((A['status']=='dropped_op_key_dup').sum()):,}). Collection-stage statuses are unchanged (replay of the committed run).",
         "- Out of scope: exam #1-#7 pools beyond the R13 train/val/v3eval rows, gate sets, and the r12 and earlier corpora.\n"]
    open(os.path.join(OUT, "master-summary.md"), "w").write("\n".join(L))
    print(tab.to_string()); print(json.dumps(R["headline"], indent=1, default=str))
    log("done")


if __name__ == "__main__":
    main()
