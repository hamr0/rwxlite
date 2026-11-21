#!/usr/bin/env python3
"""Round 16 v2 rating, laptop side: v1 ratings of the ops that stayed + new bge logits of the ops added in v2 -> data/r16/pick/bge-rating-v2.parquet,
rating-report-v2.md, rating-summary-v2.json. Same teacher (r15 bge, ckpt sha d53deafc...), same mechanical (rwxmap 1c25be1), same T 1.36 as v1.
  data/r16/scratch/venv/bin/python r16/rate_report_v2.py --chunks DIR --mech data/r16/scratch/rate-v2/mech.jsonl --texts data/r16/scratch/rate-v2/texts.jsonl [--rate-seconds S]
Row order of chunks = texts.jsonl = mech.jsonl = the ops in data/r16/pick/added-v2.csv (dev rows first, then the pick), as r16/rate_prep_v2.py wrote them."""
import argparse, glob, json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rate_report as RR  # noqa: E402

D = RR.D


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True); ap.add_argument("--mech", required=True); ap.add_argument("--texts", required=True)
    ap.add_argument("--T", type=float, default=1.36)
    ap.add_argument("--rate-seconds", type=float, default=None)
    a = ap.parse_args()
    Z = np.concatenate([np.load(f) for f in sorted(glob.glob(os.path.join(a.chunks, "chunk-*.npy")))]).astype(np.float64)
    mech = pd.read_json(a.mech, lines=True)
    assert len(Z) == len(mech) == sum(1 for _ in open(a.texts)), (len(Z), len(mech))
    rd = lambda f: pd.read_csv(os.path.join(D, f), dtype=str, keep_default_na=False)
    dev2, pick2 = rd("dev-en/dev-ops-v2.csv.gz"), rd("pick/new-300k-v2.csv.gz")
    allops = pd.concat([dev2.assign(grp="dev"), pick2.assign(grp="new")], ignore_index=True)
    assert allops["op_id"].is_unique and len(dev2) == 4475 and len(pick2) == 300000
    added = pd.read_csv(os.path.join(D, "pick", "added-v2.csv"), dtype=str)["op_id"]
    ops = allops.set_index("op_id", drop=False).loc[mech["op_id"].to_numpy()].reset_index(drop=True)
    assert set(mech["op_id"]) == set(added) and (ops["op_id"].to_numpy() == mech["op_id"].to_numpy()).all()
    new = RR.rating_frame(Z, mech, ops, a.T)
    v1 = pd.read_parquet(os.path.join(D, "pick", "bge-rating.parquet"))
    keep_ids = set(allops["op_id"]) - set(added)
    old = v1[v1["op_id"].isin(keep_ids)].copy()
    assert len(old) == len(keep_ids), (len(old), len(keep_ids))  # every op that stayed from v1 has a v1 rating
    # an op that moved between dev and pick keeps its probabilities; its part follows the v2 set
    grp = allops.set_index("op_id")["grp"]
    vk = allops.set_index("op_id")["vendor_kind"]
    old["grp"] = old["op_id"].map(grp)
    old["part"] = np.where(old["grp"] == "dev", "dev", np.where(old["op_id"].map(vk) == "domain", "new_a_domain", "new_b_hobby"))
    for c in ["p1_r", "p1_w", "p1_x", "pT_r", "pT_w", "pT_x", "ptop_T1", "ptop_T"]:
        old[c] = old[c].astype("float64")
    df = pd.concat([old, new], ignore_index=True)
    # same row order as the v2 files: dev rows, then the pick
    df["_o"] = df["op_id"].map(pd.Series(range(len(allops)), index=allops["op_id"]))
    df = df.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    assert len(df) == 304475 and df["op_id"].is_unique and set(df["op_id"]) == set(allops["op_id"])
    assert (df["grp"].to_numpy() == allops["grp"].to_numpy()).all()
    outp = os.path.join(D, "pick", "bge-rating-v2.parquet")
    RR.save_parquet(df, outp)
    RR.write_report(df, a.T, None, outp, os.path.join(D, "pick", "rating-report-v2.md"), os.path.join(D, "pick", "rating-summary-v2.json"),
                    title="# Round 16 rating (v2): r15 bge teacher on the cleaned new pick and dev set")
    extra = (f"\n## v2 provenance\n\nOf the {len(df)} rows, {len(old)} keep their v1 rating (same teacher, same mechanical, same T) and {len(new)} were rated again in v2 "
             f"(dev {int((new.grp=='dev').sum())}, pick {int((new.grp=='new').sum())})"
             + (f"; scoring time for the new rows on the server: {a.rate_seconds/3600:.2f} h" if a.rate_seconds else "") + ".\n")
    with open(os.path.join(D, "pick", "rating-report-v2.md"), "a") as f:
        f.write(extra)


if __name__ == "__main__":
    main()
