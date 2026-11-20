#!/usr/bin/env python3
"""r15 picker: draw a diverse training set from the master sheet (table work only, no labelling/model).
Reads data/r15/master/ops-r15-master.parquet, writes data/r15/picks/pick-<n>-<seed>.csv.gz + pick-<n>-<seed>-report.json.
Vendor quota by water-filling (cap found by binary search so the total is n; small vendors taken whole), then
stratified round-robin over (method, first path segment) inside each vendor.  Deterministic from --seed.
Shares are enforced by lowering per-class caps (title vendors, each source, cloud) and re-filling.
Re-run after the rwxmap flags land (master.py applies them):  python r15/pick.py --n 200000 --seed 1
Dry run (report only):  python r15/pick.py --n 200000 --seed 1 --dry-run
"""
import argparse, json, os, re, time
import numpy as np
import pandas as pd

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
D = os.path.join(REPO, "data", "r15")
MASTER = os.path.join(D, "master", "ops-r15-master.parquet")
OUTD = os.path.join(D, "picks")
CLOUD = {"alibaba", "huawei"}
SEG_SKIP = re.compile(r"^(api|rest|v\d+(\.\d+)*|\{\})$")


def eligible_mask(df, a):
    fl = df["flags"].fillna("")
    m = pd.Series(True, index=df.index)
    if not a.any_lang:
        m &= df["lang"] == "en"
    if not a.allow_no_text:
        m &= df["has_text"].astype(bool)
    if not a.include_dups:
        m &= df["dup_of"].fillna("") == ""
    if not a.allow_junk_domain:
        m &= ~fl.str.contains("junk_domain")
    if not a.allow_rpc:
        m &= ~fl.str.contains(r"(^|;)rpc(;|$)")
    if not a.allow_non_http:
        m &= ~fl.str.contains("non_http_method")
    return m


def fill_cap(sizes, n):
    """largest integer c with sum(min(s,c)) <= n; returns (c, leftover) ; leftover distributed to vendors with s>c."""
    if sizes.sum() <= n:
        return int(sizes.max()) if len(sizes) else 0, 0
    lo, hi = 0, int(sizes.max())
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if np.minimum(sizes, mid).sum() <= n:
            lo = mid
        else:
            hi = mid - 1
    return lo, int(n - np.minimum(sizes, lo).sum())


def allocate(v, n, title_share, max_source_share, max_cloud_share):
    """v: DataFrame(vendor_id, size, kind, src).  Returns int quota array, report info."""
    size = v["size"].to_numpy()
    classes = {"title": (v["kind"] == "title").to_numpy()}
    for s in v["src"].unique():
        classes["src:" + s] = (v["src"] == s).to_numpy()
    classes["cloud"] = v["src"].isin(CLOUD).to_numpy()
    limits = {"title": title_share * n, "cloud": max_cloud_share * n}
    for s in v["src"].unique():
        limits["src:" + s] = max_source_share * n
    ccap = {k: np.inf for k in classes}
    for _ in range(40):
        eff = np.full(len(v), np.inf)
        for k, msk in classes.items():
            eff = np.where(msk, np.minimum(eff, ccap[k]), eff)
        lim = np.minimum(size, eff)
        c, _ = fill_cap(lim, n)
        q = np.minimum(lim, c)
        changed = False
        for k, msk in classes.items():
            if q[msk].sum() > limits[k] + 0.5:
                sub = np.minimum(size[msk], np.minimum(ccap[k], np.inf))
                cc, _ = fill_cap(sub, int(limits[k]))
                if cc < ccap[k]:
                    ccap[k] = cc
                    changed = True
        if not changed:
            break
    return lim, c, ccap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--any-lang", action="store_true", help="do not require lang=en")
    ap.add_argument("--allow-no-text", action="store_true")
    ap.add_argument("--include-dups", action="store_true", help="include rows whose spec is a near-duplicate (dup_of set)")
    ap.add_argument("--allow-junk-domain", action="store_true")
    ap.add_argument("--allow-rpc", action="store_true")
    ap.add_argument("--allow-non-http", action="store_true")
    ap.add_argument("--title-share", type=float, default=0.3)
    ap.add_argument("--max-source-share", type=float, default=0.6)
    ap.add_argument("--max-cloud-share", type=float, default=0.1)
    ap.add_argument("--master", default=MASTER)
    a = ap.parse_args()
    t0 = time.time()
    df = pd.read_parquet(a.master)
    mrep_path = os.path.join(os.path.dirname(a.master), "master-report.json")
    mrep = json.load(open(mrep_path)) if os.path.exists(mrep_path) else {}
    flagged_applied = bool(mrep.get("rwxmap_flagged_file"))
    rep = {"n_requested": a.n, "seed": a.seed, "args": {k: v for k, v in vars(a).items()},
           "provisional": not flagged_applied,
           "provisional_note": ("rwxmap flags applied in master (%s specs dropped)" % mrep.get("rwxmap_flagged_specs_listed")
                                if flagged_applied else "PROVISIONAL: master was built without data/r15/rwxmap-flagged.txt; rebuild master then re-run pick"),
           "master_rows": len(df)}

    # eligibility counts under each switch
    import copy
    sw = {"defaults": {}, "any_lang": {"any_lang": True}, "allow_no_text": {"allow_no_text": True},
          "include_dups": {"include_dups": True}, "allow_junk_domain": {"allow_junk_domain": True},
          "allow_rpc": {"allow_rpc": True}, "allow_non_http": {"allow_non_http": True},
          "all_switches_on": {"any_lang": True, "allow_no_text": True, "include_dups": True, "allow_junk_domain": True,
                              "allow_rpc": True, "allow_non_http": True}}
    base = {k: False for k in ["any_lang", "allow_no_text", "include_dups", "allow_junk_domain", "allow_rpc", "allow_non_http"]}
    rep["eligible_under_switch"] = {}
    for name, o in sw.items():
        aa = argparse.Namespace(**{**base, **o})
        m = eligible_mask(df, aa)
        rep["eligible_under_switch"][name] = {"ops": int(m.sum()), "vendors": int(df.loc[m, "vendor_id"].nunique())}
    m = eligible_mask(df, a)
    e = df[m].copy()
    rep["eligible"] = {"ops": len(e), "vendors": int(e["vendor_id"].nunique())}
    n = min(a.n, len(e))

    # vendor table
    e["_src"] = e["source"]
    maj = e.groupby("vendor_id")["_src"].agg(lambda s: s.value_counts().index[0])
    v = e.groupby("vendor_id").agg(size=("op_id", "size"), kind=("vendor_kind", "first")).reset_index()
    v["src"] = v["vendor_id"].map(maj)
    lim, c, ccap = allocate(v, n, a.title_share, a.max_source_share, a.max_cloud_share)
    base_q = np.minimum(lim, c).astype(int)
    # distribute the integer remainder to vendors that still have room (seeded order)
    rest = int(n - base_q.sum())
    rng = np.random.default_rng(a.seed)
    room = np.flatnonzero(lim > base_q)
    if rest > 0 and len(room):
        take = rng.permutation(room)[:rest]
        base_q[take] += 1
    v["quota"] = base_q
    rep["quota"] = {"water_level_cap": int(c), "class_caps": {k: (None if np.isinf(x) else int(x)) for k, x in ccap.items()},
                    "total_quota": int(base_q.sum()), "shortfall": int(n - base_q.sum())}

    # stratified round-robin within vendor
    seg = e["path_norm"].str.split("/")
    def first_seg(parts):
        for p in parts[1:]:
            if p and not SEG_SKIP.match(p):
                return p
        return ""
    e["_stratum"] = e["method_norm"] + "|" + seg.map(first_seg)
    e["_r"] = pd.util.hash_pandas_object(pd.Series(f"{a.seed}|") + e["op_id"].reset_index(drop=True), index=False).to_numpy()
    e = e.sort_values(["vendor_id", "_stratum", "_r"])
    e["_rank_in_stratum"] = e.groupby(["vendor_id", "_stratum"], sort=False).cumcount()
    e = e.sort_values(["vendor_id", "_rank_in_stratum", "_r"])
    e["_rank_in_vendor"] = e.groupby("vendor_id", sort=False).cumcount()
    e = e.merge(v[["vendor_id", "quota"]], on="vendor_id")
    pick = e[e["_rank_in_vendor"] < e["quota"]].drop(columns=[c_ for c_ in e.columns if c_.startswith("_")] + ["quota"])
    pick = pick.sort_values(["vendor_id", "op_id"]).reset_index(drop=True)

    pv = pick.groupby("vendor_id").size()
    rep["pick"] = {
        "total": len(pick), "vendors": int(pick["vendor_id"].nunique()),
        "vendor_kind_split_ops": pick["vendor_kind"].value_counts().to_dict(),
        "vendor_kind_split_vendors": pick.groupby("vendor_kind")["vendor_id"].nunique().to_dict(),
        "source_split": pick["source"].value_counts().to_dict(),
        "source_share": {k: round(x / len(pick), 4) for k, x in pick["source"].value_counts().items()},
        "cloud_share": round(float(pick["source"].isin(CLOUD).mean()), 4),
        "title_share": round(float((pick["vendor_kind"] == "title").mean()), 4),
        "method_split": pick["method_norm"].value_counts().to_dict(),
        "ops_per_vendor": {"min": int(pv.min()), "median": float(pv.median()), "mean": round(float(pv.mean()), 2),
                           "p90": float(pv.quantile(0.9)), "p99": float(pv.quantile(0.99)), "max": int(pv.max())},
        "vendors_taken_whole": int((pv.reindex(v["vendor_id"]).to_numpy() == v["size"].to_numpy()).sum()),
        "dup_rows": int((pick["dup_of"] != "").sum()), "seconds": round(time.time() - t0),
    }
    os.makedirs(OUTD, exist_ok=True)
    stem = f"pick-{a.n}-{a.seed}"
    if a.dry_run:
        rep["dry_run"] = True
        print(json.dumps(rep, indent=1, default=int))
        return
    pick.to_csv(os.path.join(OUTD, stem + ".csv.gz"), index=False, compression="gzip")
    json.dump(rep, open(os.path.join(OUTD, stem + "-report.json"), "w"), indent=1, default=int)
    print(json.dumps(rep, indent=1, default=int))


if __name__ == "__main__":
    main()
