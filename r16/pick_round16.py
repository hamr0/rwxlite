#!/usr/bin/env python3
"""r16 pick: dev set (English, GitHub file), new ~300k pick, old-row replay list. No labelling, no training. Deterministic (seed 16).
Needs pandas + pyarrow (scratch venv):  /tmp/claude-1000/r16venv/bin/python r16/pick_round16.py
Inputs : data/r16/ops-r16-github.parquet, rwxmap exam #8 drop list (sha pinned), data/round15/train.parquet, data/r16/review/confident.csv.gz
Outputs: data/r16/dev-en/{dev-ops.csv.gz,dev-vendors.csv}, data/r16/pick/{new-300k.csv.gz,old-replay-ids.csv,pick-report.json}
Order: drop-list specs -> dev set (whole vendors) -> pick (a) all domain-vendor ops, (b) hobby fill, <=20 per vendor by water-filling.
"""
import argparse, collections, csv, gzip, hashlib, io, json, os, random, re, sys
import numpy as np, pandas as pd

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick_dev as PD  # exam #8 matcher (hits8, labels_of) reused unchanged

D = os.path.join(REPO, "data")
OPS = os.path.join(D, "r16", "ops-r16-github.parquet")
DROP = "/home/hamr/PycharmProjects/rwxmap/poc/exam8-r16-check/drop-list.csv"
DROP_SHA = "75d5fc7010aef75fa78fb20734fc4aa3cf40e9c0e231e83bb4301456e6ef9d3d"
DROP_OPS = 4680
TRAIN = os.path.join(D, "round15", "train.parquet")
CONF = os.path.join(D, "r16", "review", "confident.csv.gz")
OUT_DEV = os.path.join(D, "r16", "dev-en")
OUT_PICK = os.path.join(D, "r16", "pick")
ACC = re.compile(r"polic|role|permission|grant|(?<![a-z])acl|access|member")  # same match as the round 16 review (review.py)


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


def l1(a, b):
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=16)
    ap.add_argument("--dev-ops", type=int, default=4000)
    ap.add_argument("--dev-vendors", type=int, default=200)
    ap.add_argument("--dev-domain-share", type=float, default=0.70)
    ap.add_argument("--dev-cap", type=int, default=30)
    ap.add_argument("--dev-min-ops", type=int, default=12)
    ap.add_argument("--dev-cands", type=int, default=1000)
    ap.add_argument("--pick-total", type=int, default=300000)
    ap.add_argument("--hobby-cap", type=int, default=20)
    ap.add_argument("--domain-cap", type=int, default=300)
    ap.add_argument("--replay", type=int, default=60000)
    a = ap.parse_args()
    os.makedirs(OUT_DEV, exist_ok=True); os.makedirs(OUT_PICK, exist_ok=True)
    rep = {"seed": a.seed, "script": "r16/pick_round16.py"}

    # ---------- inputs + drop list
    assert sha(DROP) == DROP_SHA, "drop list sha changed"
    dl = pd.read_csv(DROP)
    df = pd.read_parquet(OPS)
    rep["inputs"] = {"ops_csv_gz_sha256": sha(OPS.replace(".parquet", ".csv.gz")), "ops_parquet_sha256": sha(OPS), "ops_rows": len(df), "drop_list_sha256": DROP_SHA, "drop_list_specs": len(dl),
                     "drop_list_ops_listed": int(dl["ops"].sum())}
    assert len(df) == 807949 and rep["inputs"]["ops_csv_gz_sha256"].startswith("8aa27faa")
    assert len(dl) == 260 and int(dl["ops"].sum()) == DROP_OPS
    dsh = set(dl["spec_sha256"])
    hit = df["spec_sha256"].isin(dsh)
    rep["drop_list"] = {"ops_dropped_from_file": int(hit.sum()), "specs_matched": int(df.loc[hit, "spec_sha256"].nunique()),
                        "expected_ops": DROP_OPS, "matches_expected": bool(hit.sum() == DROP_OPS)}
    df = df[~hit].reset_index(drop=True)
    assert not df["spec_sha256"].isin(dsh).any()
    rep["after_drop"] = {"ops": len(df), "vendors": int(df.vendor_key.nunique())}
    # basic eligibility (file is already filtered; assert it)
    assert df["has_text"].all() and (df["dup_of"].fillna("") == "").all() and not df["flags"].fillna("").str.contains("junk_domain|rpc|non_http").any()
    assert (df["lang"] == "en").all() and df["op_id"].is_unique
    vsize = df.groupby("vendor_key").size()
    vkind = df.groupby("vendor_key")["vendor_kind"].first()
    assert (df.groupby("vendor_key")["vendor_kind"].nunique() == 1).all()

    # ---------- 1. DEV SET (whole vendors, <=30 random ops each)
    pool_m = mix(df["method_norm"])
    cand = vsize[vsize >= a.dev_min_ops].index
    cd = sorted(v for v in cand if vkind[v] == "domain")
    ch = sorted(v for v in cand if vkind[v] != "domain")
    kind_h = collections.Counter(vkind[v] for v in ch)
    by = {v: g.index.to_numpy() for v, g in df.groupby("vendor_key", sort=True)}
    n_dom = round(a.dev_vendors * a.dev_domain_share)
    n_hob = a.dev_vendors - n_dom
    method = df["method_norm"].to_numpy()

    def draw(i):
        rng = random.Random("dev-%d-%d" % (a.seed, i))
        vs = rng.sample(cd, n_dom) + rng.sample(ch, n_hob)
        sel = {}
        for v in vs:
            ix = by[v]
            sel[v] = np.array(sorted(rng.sample(list(ix), a.dev_cap))) if len(ix) > a.dev_cap else ix
        return sel
    best = None
    for i in range(a.dev_cands):
        sel = draw(i)
        ix = np.concatenate(list(sel.values()))
        m = mix(pd.Series(method[ix]))
        sc = l1(m, pool_m) + 5 * abs(len(ix) - a.dev_ops) / a.dev_ops
        if best is None or sc < best[0]:
            best = (sc, i, sel)
    _, bi, devsel = best
    dev_ix = np.sort(np.concatenate(list(devsel.values())))
    dev = df.iloc[dev_ix]
    dev_v = set(devsel)
    write_csv_gz(dev, os.path.join(OUT_DEV, "dev-ops.csv.gz"))
    vrows = []
    for v in sorted(devsel):
        g = df.iloc[by[v]]
        f = lambda k: "|".join(sorted({x for s in g[k] for x in re.split(r"[|;,]", s) if x.strip()}))
        vrows.append([v, vkind[v], "github", "github", len(g), len(devsel[v])] + [f(k) for k in
                     ["servers_domains", "contact_domain", "logo_domain", "spec_title", "title_norm", "repo_owner", "repo_url"]])
    pd.DataFrame(vrows, columns=["vendor_key", "vendor_kind", "source_family", "sources", "pool_ops", "dev_ops", "servers_domains", "contact_domains",
                                 "logo_domains", "spec_titles", "title_norms", "repo_owners", "repo_urls"]).to_csv(
        os.path.join(OUT_DEV, "dev-vendors.csv"), index=False, lineterminator="\n")
    dvk = collections.Counter(vkind[v] for v in dev_v)
    rep["dev"] = {"vendors": len(dev_v), "ops": len(dev), "vendors_by_kind": dict(dvk), "ops_by_kind": dev["vendor_kind"].value_counts().to_dict(),
                  "domain_vendor_share": round(dvk["domain"] / len(dev_v), 4), "domain_op_share": round(float((dev.vendor_kind == "domain").mean()), 4),
                  "cap": a.dev_cap, "min_pool_ops_per_vendor": a.dev_min_ops, "candidates_drawn": a.dev_cands, "chosen_candidate": bi,
                  "ops_per_vendor_min_median_max": [int(min(map(len, devsel.values()))), float(np.median([len(x) for x in devsel.values()])), int(max(map(len, devsel.values())))],
                  "method_mix": mix(dev["method_norm"]), "pool_method_mix": pool_m, "method_mix_L1_vs_pool": round(l1(mix(dev["method_norm"]), pool_m), 4),
                  "access_kw_ops": int(((dev.path + " " + dev.operationId + " " + dev.summary).str.lower().str.contains(ACC)).sum())}

    # ---------- 2. NEW PICK
    rest = df[~df["vendor_key"].isin(dev_v)]
    dom = rest[rest.vendor_kind == "domain"]
    hob = rest[rest.vendor_kind != "domain"]
    assert dom.groupby("vendor_key").size().max() <= a.domain_cap
    need = a.pick_total - len(dom)
    hs = hob.groupby("vendor_key").size().to_numpy()
    # water-filling: largest level c <= hobby_cap with sum(min(size,c)) <= need; vendors keep their natural sizes below c
    lo, hi = 0, a.hobby_cap
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if np.minimum(hs, mid).sum() <= need:
            lo = mid
        else:
            hi = mid - 1
    c = lo
    cap_binds_at_20 = bool(np.minimum(hs, a.hobby_cap).sum() <= need)
    quota = {v: min(n, c) for v, n in hob.groupby("vendor_key").size().items()}
    left = need - sum(quota.values())
    rng = random.Random("pick-%d" % a.seed)
    if left > 0 and not cap_binds_at_20:  # one extra op for a seeded subset of vendors that still have room, so the total is exact
        room = sorted(v for v, n in hob.groupby("vendor_key").size().items() if n > c)
        rng.shuffle(room)
        for v in room[:left]:
            quota[v] += 1
        left = need - sum(quota.values())
    take = []
    for v, g in hob.groupby("vendor_key", sort=True):
        q = quota[v]
        ix = g.index.to_numpy()
        take.append(ix if q >= len(ix) else np.array(rng.sample(list(ix), q)))
    hob_pick = df.loc[np.sort(np.concatenate(take))]
    new = pd.concat([dom, hob_pick]).sort_values("op_id")
    part = np.where(new["vendor_kind"] == "domain", "a_domain", "b_hobby")
    assert not set(new.vendor_key) & dev_v and not new["spec_sha256"].isin(dsh).any()
    assert new.groupby("vendor_key").size().max() <= a.domain_cap
    assert hob_pick.groupby("vendor_key").size().max() <= a.hobby_cap and dom.groupby("vendor_key").size().max() <= a.domain_cap
    assert new["op_id"].is_unique and not set(new.op_id) & set(dev.op_id)
    # exam #8 matcher on every op of dev + new pick (whole label/domain/repo and substring audit)
    chk = pd.concat([dev, new])
    for r in chk.to_dict("records"):
        assert PD.hits8(r) == (set(), set()), r["op_id"]
    write_csv_gz(new, os.path.join(OUT_PICK, "new-300k.csv.gz"))
    ppv = new.groupby("vendor_key").size()
    hv = hob_pick.groupby("vendor_key").size()
    rep["pick"] = {"total_ops": len(new), "total_vendors": int(new.vendor_key.nunique()), "target": a.pick_total,
                   "part_a_domain": {"ops": len(dom), "vendors": int(dom.vendor_key.nunique()), "cap": a.domain_cap, "method_mix": mix(dom.method_norm)},
                   "part_b_hobby": {"ops": len(hob_pick), "vendors": int(hob_pick.vendor_key.nunique()), "need": int(need), "water_level": int(c),
                                    "level_is_the_20_cap": cap_binds_at_20, "extra_ops_leftover": int(left),
                                    "hobby_vendors_available": int(len(hs)), "hobby_ops_available": int(hs.sum()),
                                    "ops_if_all_at_cap_20": int(np.minimum(hs, a.hobby_cap).sum()),
                                    "vendors_by_kind": hob_pick.groupby("vendor_kind").vendor_key.nunique().to_dict(), "ops_by_kind": hob_pick.vendor_kind.value_counts().to_dict(),
                                    "ops_per_vendor_median_mean_max": [float(hv.median()), round(float(hv.mean()), 2), int(hv.max())],
                                    "method_mix": mix(hob_pick.method_norm)},
                   "method_mix": mix(new.method_norm), "ops_per_vendor_median_mean_max": [float(ppv.median()), round(float(ppv.mean()), 2), int(ppv.max())],
                   "top10_vendor_share": round(float(ppv.sort_values(ascending=False).head(10).sum() / len(new)), 4),
                   "licence_ops": new.licence.value_counts().head(6).to_dict(),
                   "access_kw_ops": int(((new.path + " " + new.operationId + " " + new.summary).str.lower().str.contains(ACC)).sum())}
    rep["pick_part_counts_domain_cap_300_note"] = "the 300/vendor cap was applied in collection; asserted here"

    # ---------- 3. OLD REPLAY
    tr = pd.read_parquet(TRAIN, columns=["id", "src", "label", "weight", "r15_tier", "path", "operationId", "summary"])
    assert len(tr) == 302211 and tr["id"].is_unique
    txt = (tr.path.fillna("") + " " + tr.operationId.fillna("") + " " + tr.summary.fillna("")).str.lower()
    acc = txt.str.contains(ACC, regex=True).to_numpy()
    tier = tr.r15_tier.fillna("")
    hard_tier = ((tr.src == "r15") & (tier != "") & (tier != "agree3")).to_numpy()
    hard_w3 = ((tr.src == "r15") & (tier == "agree3") & (tr.weight > 1)).to_numpy()  # D141-changed rows that count x3
    conf_ids = set(pd.read_csv(CONF, usecols=["id"])["id"])
    assert len(conf_ids) == 755 and conf_ids <= set(tr["id"])
    hard = hard_tier | acc | hard_w3
    reason = np.where(hard_tier & acc, "tier_" + tier.where(hard_tier, "") + "+access", np.where(hard_tier, "tier_" + tier.where(hard_tier, ""),
              np.where(acc & hard_w3, "access+agree3_w3", np.where(acc, "access", np.where(hard_w3, "agree3_w3", "")))))
    rest_ix = np.flatnonzero(~hard)
    nfill = a.replay - int(hard.sum())
    assert nfill > 0, "hard rows exceed the replay size"
    # fill: seeded random sample of the rest, split r13/r15 in proportion to the full 302,211 (102,668 / 199,543)
    rng2 = np.random.default_rng(a.seed)
    srcs = tr.src.to_numpy()
    share13 = (srcs == "r13").mean()
    hard13 = int((hard & (srcs == "r13")).sum())
    # target r13 total = proportional share of the whole replay; fill from r13 rest = target - hard13 (never below 0)
    t13 = int(round(a.replay * share13))
    f13 = min(max(t13 - hard13, 0), int(((~hard) & (srcs == "r13")).sum()))
    f15 = nfill - f13
    r13_rest = np.flatnonzero((~hard) & (srcs == "r13")); r15_rest = np.flatnonzero((~hard) & (srcs == "r15"))
    pick13 = rng2.choice(r13_rest, f13, replace=False); pick15 = rng2.choice(r15_rest, f15, replace=False)
    fill_mask = np.zeros(len(tr), bool); fill_mask[pick13] = True; fill_mask[pick15] = True
    sel = hard | fill_mask
    out = pd.DataFrame({"id": tr["id"][sel].to_numpy(), "src": srcs[sel], "label": tr.label[sel].to_numpy(), "weight": tr.weight[sel].to_numpy(),
                        "r15_tier": tier[sel].to_numpy(), "reason": np.where(hard[sel], reason[sel], "random_fill"),
                        "is_access": acc[sel], "confident_disagreement": tr["id"][sel].isin(conf_ids).to_numpy()})
    out = out.sort_values("id").reset_index(drop=True)
    assert len(out) == a.replay and out["id"].is_unique and int(out.confident_disagreement.sum()) <= 755
    out.to_csv(os.path.join(OUT_PICK, "old-replay-ids.csv"), index=False, lineterminator="\n")
    rep["old_replay"] = {"rows": len(out), "target": a.replay, "hard_rows": int(hard.sum()), "hard_tier_rows": int(hard_tier.sum()),
                         "access_rows_in_train": int(acc.sum()), "agree3_weight3_rows_in_train": int(hard_w3.sum()), "hard_by_reason": out[out.reason != "random_fill"].reason.value_counts().to_dict(),
                         "fill_rows": nfill, "fill_r13": f13, "fill_r15": f15, "by_src": out.src.value_counts().to_dict(), "train_src_share_r13": round(float(share13), 4),
                         "label_mix": out.label.value_counts().to_dict(), "access_rows_in_replay": int(out.is_access.sum()),
                         "confident_disagreement_in_replay": int(out.confident_disagreement.sum()), "confident_disagreement_total": len(conf_ids),
                         "note": "hard = r15 tier != agree3 (sonnet, opus_agree, strict) + access words (review ACC regex) + agree3 rows with weight 3 (D141-changed); r13 rows carry no tier"}

    rep["asserts_passed"] = ["drop-list sha and 260 specs / 4,680 ops listed", "no drop-list spec in dev, new pick (or anywhere downstream of the file)",
                             "no dev vendor in the new pick; no dev op in the pick", "exam #8 matcher (pick_dev.hits8) 0 hits on dev and pick incl. substring audit",
                             "domain cap 300 and hobby cap 20 hold", "replay ids unique, 755 confident ids exist in train"]
    rep["outputs_sha256"] = {n: sha(os.path.join(OUT_PICK, n)) for n in ["new-300k.csv.gz", "old-replay-ids.csv"]}
    rep["outputs_sha256"].update({"dev-en/" + n: sha(os.path.join(OUT_DEV, n)) for n in ["dev-ops.csv.gz", "dev-vendors.csv"]})
    json.dump(rep, open(os.path.join(OUT_PICK, "pick-report.json"), "w"), indent=1, sort_keys=True, default=int)
    print(json.dumps({k: rep[k] for k in ["drop_list", "after_drop", "dev", "pick", "old_replay"]}, indent=1, sort_keys=True, default=int))


if __name__ == "__main__":
    main()
