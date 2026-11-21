#!/usr/bin/env python3
"""Round 16 rating, laptop side: raw bge logits (server chunks) + mechanical opinion -> data/r16/pick/bge-rating.parquet and rating-report.md.
  /tmp/claude-1000/r16venv/bin/python r16/rate_report.py --chunks DIR --mech mech.jsonl --texts texts.jsonl
Order of rows = texts.jsonl = mech.jsonl (dev rows first, then the new pick). Classes: 0 r, 1 w, 2 x (danger r<w<x)."""
import argparse, glob, json, os, re, hashlib
import numpy as np, pandas as pd

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
D = os.path.join(REPO, "data", "r16")
L = "rwx"
ACC = re.compile(r"polic|role|permission|grant|(?<![a-z])acl|access|member")


def sm(Z, T):
    z = Z / T; z = z - z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)


def tab(df):
    return "```\n" + df.to_string() + "\n```\n"


def write_report(df, T, rate_seconds, outp, md, js, title="# Round 16 rating: r15 bge teacher on the new pick and the dev set"):
    """Report + summary json from a rating frame (columns as built in main). Shared by v1 (main below) and r16/rate_report_v2.py."""
    cats = ["<0.7", "0.7-0.9", ">=0.9"]
    df = df.assign(band_T1=pd.Categorical(df["band_T1"].astype(str), categories=cats, ordered=True), band_T=pd.Categorical(df["band_T"].astype(str), categories=cats, ordered=True))
    new = df[df.grp == "new"]
    R = []
    R.append(title + "\n")
    R.append(f"Rows {len(df)} (dev {int((df.grp=='dev').sum())}, new pick {len(new)}). Teacher: r15 bge-base `ckpt-r15-teacher/final`, raw logits at batch 64, max_len 128. Text = `formatText(op, lean, 1)` with the lean of rwxmap **1c25be1** (same as r15, prereg 7.2). T = 1 and T = {T} (r15 teacher val-fit; the r16 review used 1.36). Mechanical = rwxmap `classifyOperations` at 1c25be1. Letters r < w < x in danger; `bge_looser` = bge says safer than mechanical (a possible x->w leak if mech is right), `bge_tighter` = the reverse. Argmax is the same at every T; only confidence changes. Nothing here is a label.\n")
    if rate_seconds: R.append(f"Scoring time on the server: {rate_seconds/3600:.2f} h.\n")
    R.append("## 1. Confidence of bge (p_top)\n")
    for Tn, col in [("T=1", "band_T1"), ("T=%s" % T, "band_T")]:
        t = pd.crosstab(df.part, df[col]); t["total"] = t.sum(1); t.loc["new_all"] = t.loc[["new_a_domain", "new_b_hobby"]].sum()
        R.append(f"\n### {Tn}: rows by band\n" + tab(t) + "\nShare:\n" + tab((t.div(t.total, axis=0) * 100).round(1)))
    R.append("\n## 2. bge vs mechanical\n")
    g = df.groupby("part").agg(rows=("op_id", "size"), disagree=("disagree", "sum"), looser=("direction", lambda s: (s == "bge_looser").sum()), tighter=("direction", lambda s: (s == "bge_tighter").sum()))
    g.loc["new_all"] = g.loc[["new_a_domain", "new_b_hobby"]].sum(); g["disagree_pct"] = (g.disagree / g.rows * 100).round(2)
    R.append(tab(g)); R.append("\nLetter pairs (mech->bge), new pick:\n" + tab(pd.crosstab(new.pair, new.part, margins=True)))
    dm = new[new.disagree]
    R.append("\nDisagreements by method and direction (new pick):\n" + tab(pd.crosstab(dm.method, dm.direction, margins=True)))
    R.append("\nDisagreement rate by method (new pick):\n" + tab(new.groupby("method").agg(rows=("op_id", "size"), disagree=("disagree", "sum")).assign(pct=lambda x: (x.disagree / x.rows * 100).round(2))))
    R.append("\nBy mechanical rule, top 15 disagreeing rules (new pick):\n" + tab(dm.groupby("mech_rule").size().sort_values(ascending=False).head(15).to_frame("disagreements")))
    hi = dm[dm.ptop_T >= 0.9]
    R.append(f"\nConfident disagreements (p_top >= 0.9 at T={T}), new pick: {len(hi)} (looser {int((hi.direction=='bge_looser').sum())}, tighter {int((hi.direction=='bge_tighter').sum())}); at T=1 p_top >= 0.9: {int((dm.ptop_T1>=0.9).sum())}.\n")
    R.append("\n## 3. Unsure rows (p_top < 0.7 at T=%s)\n" % T)
    R.append(tab(df.groupby("part").agg(rows=("op_id", "size"), unsure=("unsure_T", "sum")).assign(pct=lambda x: (x.unsure / x.rows * 100).round(2))))
    R.append("\n## 4. Access/permission rows (policy|role|permission|grant|acl|access|member in path/operationId/summary)\n")
    ac = df[df.is_access]
    R.append(f"Rows {len(ac)} (new pick {int(ac.grp.eq('new').sum())}, dev {int(ac.grp.eq('dev').sum())}); in the new pick that is {ac.grp.eq('new').sum()/len(new)*100:.2f}% of rows, {ac[ac.grp=='new'].vendor_key.nunique()} vendors.\n")
    an = ac[ac.grp == "new"]
    R.append("bge letter by method (new pick, access rows):\n" + tab(pd.crosstab(an.method, an.bge_letter, margins=True)))
    R.append("\nmech letter by method (same rows):\n" + tab(pd.crosstab(an.method, an.mech_letter, margins=True)))
    R.append("\nmech->bge pairs on access rows:\n" + tab(pd.crosstab(an.pair, an.method.where(an.method.isin(["PUT", "PATCH", "POST", "DELETE"]), "other"), margins=True)))
    R.append(f"\nAccess rows that disagree: {int(an.disagree.sum())} ({an.disagree.mean()*100:.1f}%, other rows {new[~new.is_access].disagree.mean()*100:.1f}%); access rows unsure: {int(an.unsure_T.sum())}. Mutating access rows (PUT/PATCH/POST) where bge says w: {int(((an.method.isin(['PUT','PATCH','POST'])) & (an.bge_letter=='w')).sum())} (D137 candidates: grant/widen = x).\n")
    R.append("\n## 5. Proposed Opus list (new pick only; dev is never trained on and is not sent)\n")
    n_un, n_dis = int(new.unsure_T.sum()), int(new.disagree.sum())
    both = int((new.unsure_T & new.disagree).sum())
    R.append(f"- Unsure (p_top < 0.7 at T={T}): {n_un}\n- bge != mech: {n_dis}\n- both: {both}\n- **Union (proposed): {int(new.opus.sum())} rows ({new.opus.mean()*100:.1f}% of {len(new)})**\n")
    R.append("Union by part:\n" + tab(new.groupby("part").agg(rows=("op_id", "size"), opus=("opus", "sum")).assign(pct=lambda x: (x.opus / x.rows * 100).round(1))))
    R.append("\nSmaller options (new pick): " + "; ".join([
        f"disagreements only {n_dis}", f"disagreements with p_top >= 0.7 at T={T}: {int((new.disagree & ~new.unsure_T).sum())}",
        f"only bge_looser disagreements (possible leaks): {int((new.direction=='bge_looser').sum())}",
        f"unsure at T=1 (p_top<0.7): {int((new.ptop_T1<0.7).sum())}", f"union at T=1: {int(((new.ptop_T1<0.7)|new.disagree).sum())}",
        f"union plus access rows not already in it: {int((new.opus | new.is_access).sum())}"]) + ".\n")
    R.append("\nNote: the round 15 cascade sent rows where bge, mech and R13 did not all agree to Sonnet; R13 (rwxmap mode a) is the third opinion and is not scored here (needs the rwxmap run). This list is bge vs mech plus bge's own doubt.\n")
    R.append("\nDev set (info): " + f"{int((df.grp=='dev').sum())} rows, bge vs mech disagree {int(df[df.grp=='dev'].disagree.sum())}, unsure {int(df[df.grp=='dev'].unsure_T.sum())}.\n")
    open(md, "w").write("\n".join(R))
    sh = hashlib.sha256(open(outp, "rb").read()).hexdigest()
    json.dump({"rows": len(df), "opus_union_new": int(new.opus.sum()), "unsure_new": n_un, "disagree_new": n_dis, "parquet_sha256": sh}, open(js, "w"), indent=1)
    print(json.dumps({"opus_union_new": int(new.opus.sum()), "unsure_new": n_un, "disagree_new": n_dis, "sha": sh}))



def rating_frame(Z, mech, ops, T):
    """Frame of bge probabilities + mechanical opinion per op; ops has columns grp, vendor_kind, vendor_key, method_norm, path, operationId, summary, same row order as Z and mech."""
    P1, PT = sm(Z, 1.0), sm(Z, T)
    df = pd.DataFrame({"op_id": mech.op_id, "grp": ops.grp, "vendor_kind": ops.vendor_kind, "vendor_key": ops.vendor_key, "method": ops.method_norm,
                       "mech_letter": mech.mech_letter, "mech_rule": mech.mech_rule, "mech_review": mech.mech_review,
                       "p1_r": P1[:, 0], "p1_w": P1[:, 1], "p1_x": P1[:, 2], "pT_r": PT[:, 0], "pT_w": PT[:, 1], "pT_x": PT[:, 2],
                       "bge_letter": [L[i] for i in PT.argmax(1)], "ptop_T1": P1.max(1), "ptop_T": PT.max(1)})
    assert (P1.argmax(1) == PT.argmax(1)).all()
    df["part"] = np.where(df.grp == "dev", "dev", np.where(df.vendor_kind == "domain", "new_a_domain", "new_b_hobby"))
    df["is_access"] = (ops.path + " " + ops.operationId + " " + ops.summary).str.lower().str.contains(ACC).to_numpy()
    rank = {"r": 0, "w": 1, "x": 2}
    d = df.bge_letter.map(rank) - df.mech_letter.map(rank)
    df["disagree"] = d != 0
    df["direction"] = np.where(d == 0, "agree", np.where(d < 0, "bge_looser", "bge_tighter"))  # bge less dangerous than mech = looser
    df["unsure_T"] = df.ptop_T < 0.7
    df["opus"] = df.unsure_T | df.disagree
    df["pair"] = df.mech_letter + "->" + df.bge_letter
    df["band_T1"] = pd.cut(df.ptop_T1, [0, .7, .9, 1.01], right=False, labels=["<0.7", "0.7-0.9", ">=0.9"])
    df["band_T"] = pd.cut(df.ptop_T, [0, .7, .9, 1.01], right=False, labels=["<0.7", "0.7-0.9", ">=0.9"])
    return df


def save_parquet(df, outp):
    df.drop(columns=["grp"]).assign(**{c: df[c].astype("float32") for c in ["p1_r", "p1_w", "p1_x", "pT_r", "pT_w", "pT_x", "ptop_T1", "ptop_T"]}).astype({"band_T1": str, "band_T": str}).to_parquet(outp, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True); ap.add_argument("--mech", required=True); ap.add_argument("--texts", required=True)
    ap.add_argument("--T", type=float, default=1.36)
    ap.add_argument("--rate-seconds", type=float, default=None)
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.chunks, "chunk-*.npy")))
    Z = np.concatenate([np.load(f) for f in fs]).astype(np.float64)
    mech = pd.read_json(a.mech, lines=True)
    assert len(Z) == len(mech) == sum(1 for _ in open(a.texts)), (len(Z), len(mech))
    ops = pd.concat([pd.read_csv(os.path.join(D, "dev-en", "dev-ops.csv.gz"), dtype=str, keep_default_na=False).assign(grp="dev"),
                     pd.read_csv(os.path.join(D, "pick", "new-300k.csv.gz"), dtype=str, keep_default_na=False).assign(grp="new")], ignore_index=True)
    assert (ops.op_id.to_numpy() == mech.op_id.to_numpy()).all()
    df = rating_frame(Z, mech, ops, a.T)
    outp = os.path.join(D, "pick", "bge-rating.parquet")
    save_parquet(df, outp)
    write_report(df, a.T, a.rate_seconds, outp, os.path.join(D, "pick", "rating-report.md"), os.path.join(D, "pick", "rating-summary.json"))


if __name__ == "__main__":
    main()
