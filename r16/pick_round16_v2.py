#!/usr/bin/env python3
"""r16 pick v2: v1 dev + new pick cleaned of copies, then refilled. No labelling, no training. Deterministic (seed 16). v1 files are kept.
Run (scratch venv):  nice -n 19 data/r16/scratch/venv/bin/python r16/pick_round16_v2.py
Inputs : data/r16/ops-r16-github.parquet (the pool), v1 data/r16/pick/new-300k.csv.gz + data/r16/dev-en/dev-ops.csv.gz (op ids only),
         known rows (r16/opkey.py: R13 train/val/v3eval, r15 master incl. trained and holdout), exam #8 drop list (sha pinned).
Outputs: data/r16/pick/new-300k-v2.csv.gz, data/r16/dev-en/dev-ops-v2.csv.gz, dev-vendors-v2.csv, data/r16/pick/pick-report-v2.json,
         data/r16/pick/dropped-v2.csv.gz (every v1 dev/pick op removed, with the reason), data/r16/pick/added-v2.csv (op ids added).

Rules (exact key K1 = method upper + path + operationId + summary, see r16/opkey.py; the normalised key K2 is only reported, with 20 examples: they are
not copies (different summaries, often another language), so it is not a drop rule):
  dev  : drop v1 dev ops whose K1 is known; drop K1 duplicates inside dev (lowest op_id kept); refill from the SAME dev vendors (cap 30 per vendor),
         then, only if they run dry, from new vendors (same rules as v1: >= 12 clean pool ops, cap 30, ~70% domain vendors); every vendor is in the pick, so a
         new dev vendor leaves the pick (its ops that are not taken for dev are dropped there as vendor_moved_to_dev).
  pick : drop v1 pick ops whose K1 is known; whose K1 equals a dev op (dev wins); K1 duplicates inside the pick (lowest op_id kept); ops of vendors that moved to dev (taken for dev: moved_to_dev; not taken: vendor_moved_to_dev_not_taken).
         refill to 300,000 from clean unused rows only (status unused_clean: kept in the pool, not exam #8 drop list, no soft flag, not in v1 dev/pick,
         not a dev vendor, K1 not known, K1 not already in dev/pick, K1 unique among candidates). Domain vendors first (all their clean ops, cap 300),
         then hobby vendors by water-filling on the current per-vendor counts (spread thin, hobby cap 20, seeded +1 for the remainder).
"""
import argparse, collections, gzip, hashlib, io, json, os, random, re, sys
import numpy as np, pandas as pd

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opkey  # noqa: E402
import pick_dev as PD  # exam #8 matcher (hits8) reused unchanged  # noqa: E402

D = os.path.join(REPO, "data")
OPS = os.path.join(D, "r16", "ops-r16-github.parquet")
DROP = "/home/hamr/PycharmProjects/rwxmap/poc/exam8-r16-check/drop-list.csv"
DROP_SHA = "75d5fc7010aef75fa78fb20734fc4aa3cf40e9c0e231e83bb4301456e6ef9d3d"
OUT_DEV = os.path.join(D, "r16", "dev-en")
OUT_PICK = os.path.join(D, "r16", "pick")
SOFT = ["huge_spec", "odd_path", "lorem", "placeholder_text", "autogen_opid_only", "test_endpoint"]
SEED = 16


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_csv_gz(df, path):
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=6) as gz, \
         io.TextIOWrapper(gz, encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False, lineterminator="\n")


def mix(s):
    c = s.value_counts(normalize=True)
    return {k: round(float(v), 4) for k, v in c.sort_index().items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-total", type=int, default=300000)
    ap.add_argument("--dev-cap", type=int, default=30)
    ap.add_argument("--hobby-cap", type=int, default=20)
    ap.add_argument("--domain-cap", type=int, default=300)
    ap.add_argument("--dev-min-ops", type=int, default=12)
    a = ap.parse_args()
    rep = {"script": "r16/pick_round16_v2.py", "seed": SEED}

    # ------------------------------------------------------------ pool + keys
    assert sha(DROP) == DROP_SHA
    dl = pd.read_csv(DROP)
    pool = pd.read_parquet(OPS)
    assert len(pool) == 807949 and pool["op_id"].is_unique
    pool["k1"] = opkey.k1(pool)
    pool["k2"] = opkey.k2(pool)
    known = opkey.load_known(D)
    S1, S2 = opkey.known_sets(known)
    rep["known_rows"] = {k: len(v) for k, v in known.items()}
    rep["known_distinct_exact_keys"] = {k: len(v) for k, v in S1.items()}
    pool["src1"] = opkey.first_source(pool["k1"], S1)
    pool["src2"] = opkey.first_source(pool["k2"], S2)
    pool = pool.set_index("op_id", drop=False); pool.index.name = None

    v1_pick = pd.read_csv(os.path.join(OUT_PICK, "new-300k.csv.gz"), usecols=["op_id"])["op_id"]
    v1_dev = pd.read_csv(os.path.join(OUT_DEV, "dev-ops.csv.gz"), usecols=["op_id"])["op_id"]
    assert len(v1_pick) == 300000 and len(v1_dev) == 4475
    pk1, dv1 = pool.loc[v1_pick.to_numpy()], pool.loc[v1_dev.to_numpy()]
    dev_vendors = sorted(set(dv1["vendor_key"]))
    assert not set(pk1["vendor_key"]) & set(dev_vendors)
    drop_sha = set(dl["spec_sha256"])
    soft = pool["flags"].fillna("").str.contains("|".join(SOFT))
    clean_unused = ~pool["spec_sha256"].isin(drop_sha) & ~soft & ~pool.index.isin(set(v1_pick) | set(v1_dev))
    rep["pool"] = {"ops": len(pool), "exam8_drop_list_ops": int(pool["spec_sha256"].isin(drop_sha).sum()), "soft_flagged_ops": int(soft.sum()),
                   "v1_dev": len(v1_dev), "v1_pick": len(v1_pick), "clean_unused_ops": int(clean_unused.sum()),
                   "soft_flagged_ops_inside_v1_pick": int(soft.loc[v1_pick].sum()), "note": "soft-flagged rows already in the v1 pick are kept (they are not copies); refills use clean rows only"}

    # ------------------------------------------------------------ report on v1: exact vs normalised key, per source
    def key_report(df, name):
        r = {"ops": len(df), "exact_per_source": {}, "norm_per_source": {}}
        for n in opkey.KNOWN_ORDER:
            r["exact_per_source"][n] = int(sum(k in S1[n] for k in df["k1"]))
            r["norm_per_source"][n] = int(sum(k in S2[n] for k in df["k2"]))
        e = df["src1"] != ""
        nn = df["src2"] != ""
        r["exact_union"] = int(e.sum()); r["norm_union"] = int(nn.sum())
        r["norm_only_extra"] = int((nn & ~e).sum())
        r["norm_only_extra_nonempty_operationId"] = int((nn & ~e & (df["operationId"] != "")).sum())
        r["exact_first_source"] = df.loc[e, "src1"].value_counts().to_dict()
        return r
    rep["v1_key_report"] = {"dev": key_report(dv1, "dev"), "pick": key_report(pk1, "pick")}

    # normalised-only examples (20), with the known row they match
    ex = pk1[(pk1["src2"] != "") & (pk1["src1"] == "") & (pk1["operationId"] != "")]
    exs = ex.sample(20, random_state=SEED) if len(ex) >= 20 else ex
    need = {k: None for k in exs["k2"]}
    kfr = known["r15_master"]
    kk = opkey.k2(kfr)
    for i, k in enumerate(kk):
        if k in need and need[k] is None:
            need[k] = kfr.iloc[i]["summary"]
    rep["norm_only_examples"] = [{"op_id": r.op_id, "method": r.method, "path": r.path, "operationId": r.operationId, "summary": r.summary, "known_summary_r15_master": need.get(r.k2)}
                                 for r in exs.itertuples()]

    def known_mask(df):
        return df["src1"] != ""

    # ------------------------------------------------------------ DEV v2
    drops = []  # (op_id, set, reason, detail)

    def log_drop(df, st, reason, detail=None):
        for i, d in zip(df["op_id"], (df[detail] if detail else [""] * len(df))):
            drops.append((i, st, reason, d))

    km = known_mask(dv1)
    log_drop(dv1[km], "dev", "known_key", "src1")
    d1 = dv1[~km].sort_values("op_id")
    dupm = d1["k1"].duplicated(keep="first")
    log_drop(d1[dupm], "dev", "dup_in_dev")
    dev_kept = d1[~dupm]
    rep["dev_v2"] = {"v1_ops": len(dv1), "dropped_known_key": int(km.sum()), "dropped_known_exact_only": int((dv1["src1"] != "").sum()),
                     "dropped_dup_in_dev": int(dupm.sum()), "kept": len(dev_kept)}
    need_dev = len(dv1) - len(dev_kept)
    cnt = dev_kept.groupby("vendor_key").size().to_dict()
    keys_now = set(dev_kept["k1"])
    cand = pool[clean_unused & pool["vendor_key"].isin(dev_vendors) & (pool["src1"] == "")]
    rng = random.Random("dev2-%d" % SEED)
    cv = {v: sorted(g["op_id"]) for v, g in cand.groupby("vendor_key")}
    for v in cv:
        rng.shuffle(cv[v])
    added_dev = []
    order = sorted(cv)
    rng.shuffle(order)
    ptr = {v: 0 for v in cv}
    progress = True
    while len(added_dev) < need_dev and progress:
        progress = False
        for v in order:
            if len(added_dev) >= need_dev:
                break
            if cnt.get(v, 0) >= a.dev_cap:
                continue
            while ptr[v] < len(cv[v]):
                o = cv[v][ptr[v]]; ptr[v] += 1
                if pool.at[o, "k1"] in keys_now:
                    continue
                keys_now.add(pool.at[o, "k1"]); added_dev.append(o); cnt[v] = cnt.get(v, 0) + 1; progress = True
                break
    rep["dev_v2"]["refilled_from_own_vendors"] = len(added_dev)
    rep["dev_v2"]["still_short_after_own_vendors"] = need_dev - len(added_dev)
    new_dev_vendors = []
    if len(added_dev) < need_dev:
        # new dev vendors, v1 rules: >= 12 clean pool ops, cap 30 per vendor, about 70% domain vendors. Every hobby/domain vendor is in the pick (r15/r16 drew
        # from all of them), so a new dev vendor leaves the pick: its pick rows are dropped there ("vendor_moved_to_dev") and the pick is refilled from other vendors.
        fin = pool[~pool["spec_sha256"].isin(drop_sha) & ~soft & ~pool["vendor_key"].isin(dev_vendors) & (pool["src1"] == "")]
        fin = fin[~fin["k1"].isin(keys_now)]
        sizes = fin.groupby("vendor_key").size()
        kind = fin.groupby("vendor_key")["vendor_kind"].first()
        el = {"domain": [], "hobby": []}
        for v in sorted(v for v in sizes.index if sizes[v] >= a.dev_min_ops):
            el["domain" if kind[v] == "domain" else "hobby"].append(v)
        r2 = random.Random("dev2new-%d" % SEED)
        for k in el:
            r2.shuffle(el[k])
        share = rep["dev_v2"]["v1_domain_vendor_share"] = 0.70
        ptr2 = {"domain": 0, "hobby": 0}
        while len(added_dev) < need_dev:
            k = "domain" if r2.random() < share else "hobby"
            if ptr2[k] >= len(el[k]):
                k = "hobby" if k == "domain" else "domain"
            v = el[k][ptr2[k]]; ptr2[k] += 1
            g = sorted(fin.loc[fin["vendor_key"] == v, "op_id"])
            r2.shuffle(g)
            take = []
            for o in g:
                if len(take) >= min(a.dev_cap, need_dev - len(added_dev)):
                    break
                if pool.at[o, "k1"] in keys_now:
                    continue
                keys_now.add(pool.at[o, "k1"]); take.append(o)
            added_dev += take; new_dev_vendors.append(v)
    rep["dev_v2"]["new_dev_vendors"] = new_dev_vendors
    rep["dev_v2"]["refilled_from_new_vendors"] = len(added_dev) - rep["dev_v2"]["refilled_from_own_vendors"]
    dev2 = pd.concat([dev_kept, pool.loc[added_dev]]).sort_values("op_id")
    dev_vendors2 = sorted(set(dev2["vendor_key"]))
    assert dev2["op_id"].is_unique and not dev2["k1"].duplicated().any() and (dev2["src1"] == "").all()
    added_ids = set(added_dev) - set(v1_pick)  # ops that still need a rating (an op moved from the v1 pick to dev already has one)
    rep["dev_v2"].update({"ops": len(dev2), "vendors": len(dev_vendors2), "ops_by_kind": dev2["vendor_kind"].value_counts().to_dict(),
                          "method_mix": mix(dev2["method_norm"]), "method_mix_v1": mix(dv1["method_norm"])})

    # ------------------------------------------------------------ PICK v2
    p = pk1
    km = known_mask(p)
    log_drop(p[km], "pick", "known_key", "src1")
    p = p[~km]
    dkeys = set(dev2["k1"])
    in_dev = p["op_id"].isin(set(dev2["op_id"]))  # an op of a vendor that moved to dev and was taken there: it leaves the pick, it is not a copy
    log_drop(p[in_dev], "pick", "moved_to_dev")
    p = p[~in_dev]
    mv = p["vendor_key"].isin(set(dev_vendors2))
    log_drop(p[mv], "pick", "vendor_moved_to_dev_not_taken")
    p = p[~mv]
    dm = p["k1"].isin(dkeys)
    log_drop(p[dm], "pick", "dup_of_dev")
    p = p[~dm].sort_values("op_id")
    dupm = p["k1"].duplicated(keep="first")
    log_drop(p[dupm], "pick", "dup_in_pick")
    p = p[~dupm]
    rep["pick_v2"] = {"v1_ops": len(pk1), "dropped_known_key": int((known_mask(pk1)).sum()), "dropped_dup_of_dev": int(dm.sum()),
                      "moved_to_dev": int(in_dev.sum()), "dropped_vendor_moved_to_dev_not_taken": int(mv.sum()), "dropped_dup_in_pick": int(dupm.sum()), "kept": len(p)}
    kn = pk1["src1"] != ""
    rep["pick_v2"]["known_key_by_first_source_exact"] = pk1.loc[kn, "src1"].value_counts().to_dict()
    keys_pick = set(p["k1"])
    need = a.pick_total - len(p)
    pre_dom = p[p["vendor_kind"] == "domain"]
    cand = pool[clean_unused & ~pool["vendor_key"].isin(set(dev_vendors2)) & (pool["src1"] == "") & ~pool["k1"].isin(dkeys) & ~pool["k1"].isin(keys_pick)]
    cand = cand.assign(_h=[hashlib.sha256(("pick2-%d" % SEED + o).encode()).hexdigest() for o in cand["op_id"]]).sort_values("_h")
    n_before = len(cand)
    cand = cand[~cand["k1"].duplicated(keep="first")]
    rep["pick_v2"]["refill_candidates"] = {"after_filters": n_before, "after_unique_key": len(cand), "domain": int((cand["vendor_kind"] == "domain").sum()),
                                           "hobby": int((cand["vendor_kind"] != "domain").sum())}
    added = []
    # (a) domain vendors first
    cd = cand[cand["vendor_kind"] == "domain"]
    cur = p.groupby("vendor_key").size().to_dict()
    take_d = []
    for v, g in cd.groupby("vendor_key", sort=True):
        room = a.domain_cap - cur.get(v, 0)
        take_d += list(g["op_id"].iloc[:max(room, 0)])
    take_d = take_d[:need]
    added += take_d
    need -= len(take_d)
    rep["pick_v2"]["refill_domain_ops"] = len(take_d)
    # (b) hobby water-filling on current counts
    ch = cand[cand["vendor_kind"] != "domain"]
    cur_h = p[p["vendor_kind"] != "domain"].groupby("vendor_key").size().to_dict()
    av = {v: list(g["op_id"]) for v, g in ch.groupby("vendor_key", sort=True)}  # already in seeded hash order

    def add_at(c):
        return {v: max(0, min(len(av[v]), c - cur_h.get(v, 0), a.hobby_cap - cur_h.get(v, 0))) for v in av}
    lo, hi = 0, a.hobby_cap
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if sum(add_at(mid).values()) <= need:
            lo = mid
        else:
            hi = mid - 1
    c = lo
    ad = add_at(c)
    left = need - sum(ad.values())
    r3 = random.Random("pick2-%d" % SEED)
    room = sorted(v for v in av if ad[v] < len(av[v]) and cur_h.get(v, 0) + ad[v] < a.hobby_cap)
    r3.shuffle(room)
    for v in room[:left]:
        ad[v] += 1
    left = need - sum(ad.values())
    for v, n in ad.items():
        added += av[v][:n]
    rep["pick_v2"]["refill_hobby"] = {"need": int(need), "water_level": int(c), "ops": int(sum(ad.values())), "vendors": int(sum(1 for n in ad.values() if n)),
                                      "shortfall": int(left), "hobby_candidates": len(ch)}
    assert left == 0, "refill short by %d" % left
    pick2 = pd.concat([p, pool.loc[added]]).sort_values("op_id")
    added_ids |= set(added)

    # ------------------------------------------------------------ asserts
    assert len(pick2) == a.pick_total and pick2["op_id"].is_unique
    assert not pick2["k1"].duplicated().any(), "exact-key duplicate inside the pick"
    assert not pick2["k1"].isin(set(dev2["k1"])).any(), "pick op shares its exact key with a dev op"
    allk = set().union(*S1.values())
    assert not any(k in allk for k in pick2["k1"]) and not any(k in allk for k in dev2["k1"]), "pick/dev op shares its exact key with a trained/holdout row"
    assert not set(pick2["vendor_key"]) & set(dev_vendors2) and not set(pick2["op_id"]) & set(dev2["op_id"])
    assert not pick2["spec_sha256"].isin(drop_sha).any() and not dev2["spec_sha256"].isin(drop_sha).any()
    assert pick2[pick2["vendor_kind"] == "domain"].groupby("vendor_key").size().max() <= a.domain_cap
    assert pick2[pick2["vendor_kind"] != "domain"].groupby("vendor_key").size().max() <= a.hobby_cap
    assert dev2.groupby("vendor_key").size().max() <= a.dev_cap
    assert (pick2["lang"] == "en").all() and (dev2["lang"] == "en").all()
    assert not (set(pick2["op_id"]) - set(v1_pick) - added_ids)
    assert not (added_ids & (set(v1_pick) | set(v1_dev))), "an added op was already in v1 dev/pick"
    moved_to_dev = set(dev2["op_id"]) & set(v1_pick)
    assert all(clean_unused[o] for o in added_ids), "an added op is not unused_clean"
    for r in pd.concat([dev2.loc[[o for o in dev2["op_id"] if o in added_ids]], pick2.loc[[o for o in pick2["op_id"] if o in added_ids]]]).to_dict("records"):
        assert PD.hits8(r) == (set(), set()), r["op_id"]
    out_cols = [c for c in pd.read_parquet(OPS).columns]
    write_csv_gz(dev2[out_cols], os.path.join(OUT_DEV, "dev-ops-v2.csv.gz"))
    write_csv_gz(pick2[out_cols], os.path.join(OUT_PICK, "new-300k-v2.csv.gz"))
    # dev vendors table (v1 format)
    vr = []
    for v in dev_vendors2:
        g = pool[pool["vendor_key"] == v]
        f = lambda k: "|".join(sorted({x for s in g[k] for x in re.split(r"[|;,]", s) if x.strip()}))
        vr.append([v, g["vendor_kind"].iloc[0], "github", "github", len(g), int((dev2["vendor_key"] == v).sum())] + [f(k) for k in
                  ["servers_domains", "contact_domain", "logo_domain", "spec_title", "title_norm", "repo_owner", "repo_url"]])
    pd.DataFrame(vr, columns=["vendor_key", "vendor_kind", "source_family", "sources", "pool_ops", "dev_ops", "servers_domains", "contact_domains",
                              "logo_domains", "spec_titles", "title_norms", "repo_owners", "repo_urls"]).to_csv(os.path.join(OUT_DEV, "dev-vendors-v2.csv"), index=False, lineterminator="\n")
    dr = pd.DataFrame(drops, columns=["op_id", "set", "reason", "detail"])
    assert dr["op_id"].is_unique
    write_csv_gz(dr, os.path.join(OUT_PICK, "dropped-v2.csv.gz"))
    pd.DataFrame({"op_id": sorted(added_ids), "set": ["dev" if o in set(dev2["op_id"]) else "pick" for o in sorted(added_ids)]}).to_csv(
        os.path.join(OUT_PICK, "added-v2.csv"), index=False, lineterminator="\n")

    # ------------------------------------------------------------ report
    ppv = pick2.groupby("vendor_key").size()
    rep["drops_by_reason"] = dr.groupby(["set", "reason"]).size().rename("ops").reset_index().to_dict("records")
    rep["drops_known_key_by_first_source"] = dr[dr.reason == "known_key"].groupby(["set", "detail"]).size().rename("ops").reset_index().to_dict("records")
    rep["pick_final"] = {"ops": len(pick2), "vendors": int(pick2["vendor_key"].nunique()), "kept_from_v1": int(pick2["op_id"].isin(set(v1_pick)).sum()),
                         "added": int(pick2["op_id"].isin(added_ids).sum()), "dev_ops_moved_from_v1_pick": len(moved_to_dev), "domain_ops": int((pick2["vendor_kind"] == "domain").sum()),
                         "hobby_ops": int((pick2["vendor_kind"] != "domain").sum()), "method_mix": mix(pick2["method_norm"]), "method_mix_v1": mix(pk1["method_norm"]),
                         "ops_per_vendor_median_mean_max": [float(ppv.median()), round(float(ppv.mean()), 2), int(ppv.max())],
                         "top10_vendor_share": round(float(ppv.sort_values(ascending=False).head(10).sum() / len(pick2)), 4),
                         "added_by_kind": pick2[pick2["op_id"].isin(added_ids)]["vendor_kind"].value_counts().to_dict()}
    rep["asserts_passed"] = ["no pick/dev op shares the exact key with any R13 train/val/v3eval, r15 master (trained, holdout) row", "no exact-key duplicate inside the pick or inside dev, none between pick and dev",
                             "no dev vendor in the pick, no dev op in the pick", "no exam #8 drop-list spec in dev or pick", "exam #8 matcher 0 hits on every added row",
                             "every added op is unused_clean (pool, not drop list, no soft flag, not v1 dev/pick)", "caps hold: domain 300, hobby 20, dev 30", "pick total 300,000"]
    rep["outputs_sha256"] = {"pick/new-300k-v2.csv.gz": sha(os.path.join(OUT_PICK, "new-300k-v2.csv.gz")), "dev-en/dev-ops-v2.csv.gz": sha(os.path.join(OUT_DEV, "dev-ops-v2.csv.gz")),
                             "pick/dropped-v2.csv.gz": sha(os.path.join(OUT_PICK, "dropped-v2.csv.gz")), "pick/added-v2.csv": sha(os.path.join(OUT_PICK, "added-v2.csv"))}
    json.dump(rep, open(os.path.join(OUT_PICK, "pick-report-v2.json"), "w"), indent=1, sort_keys=True, default=int)
    print(json.dumps({k: rep[k] for k in ["v1_key_report", "dev_v2", "pick_v2", "pick_final", "drops_by_reason"]}, indent=1, sort_keys=True, default=int))
    print(json.dumps(rep["norm_only_examples"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
