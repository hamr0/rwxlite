"""Operation keys used to find copies of ops across sources (one definition; used by filter_github, pick_round16_v2, build_master_all).

exact key  K1 = (METHOD upper, path, operationId, summary)           empty/NaN operationId or summary -> ""
norm key   K2 = (METHOD upper, path with {..} -> {} lowercased and trailing slash dropped, operationId)

Why tuples and not hashes: the first version of the filter rule hashed "method\\0path\\0operationId\\0summary" with
pandas.util.hash_pandas_object. That hash stops at the first NUL byte (it hashes the method only), and on an object-dtype
column the "\\0" separators vanish from the concatenation, so the master side (str dtype) and the r16 side (object dtype)
never agreed: 0 matches. A python tuple set has neither problem.
"""
import os
import re
import pandas as pd

_BR = re.compile(r"\{[^}]*\}")


def _s(x):
    return x.fillna("").astype(str)


def k1(df):
    return list(zip(_s(df["method"]).str.upper(), _s(df["path"]), _s(df["operationId"]), _s(df["summary"])))


def norm_path(p):
    p = _BR.sub("{}", p).lower().rstrip("/")
    return p or "/"


def k2(df):
    return [(m, norm_path(p), o) for m, p, o in zip(_s(df["method"]).str.upper(), _s(df["path"]), _s(df["operationId"]))]


def load_known(D):
    """Rows we have trained on or hold out. Returns {source: DataFrame[method,path,operationId,summary]}.
    r15_master = all 802,196 r15 master rows (contains the trained r15 rows and the 400 holdout rows)."""
    cols = ["method", "path", "operationId", "summary"]
    out = {}
    for name, f in [("r13_train", "train.parquet"), ("r13_val", "val.parquet"), ("r13_v3eval", "v3eval.parquet")]:
        out[name] = pd.read_parquet(os.path.join(D, "round13", f), columns=cols)
    m = pd.read_parquet(os.path.join(D, "r15", "master", "ops-r15-master.parquet"), columns=["op_id"] + cols)
    tr15 = pd.read_parquet(os.path.join(D, "round15", "train.parquet"), columns=["id", "src"])
    hold = pd.read_csv(os.path.join(D, "r15", "labels", "disagree-sample-400.csv"), usecols=["op_id"])["op_id"]
    out["r15_holdout"] = m[m["op_id"].isin(set(hold))][cols]
    out["r15_trained"] = m[m["op_id"].isin(set(tr15.loc[tr15["src"] == "r15", "id"]))][cols]
    out["r15_master"] = m[cols]
    return out


KNOWN_ORDER = ["r13_train", "r13_val", "r13_v3eval", "r15_trained", "r15_holdout", "r15_master"]


def known_sets(known):
    s1 = {k: set(k1(v)) for k, v in known.items()}
    s2 = {k: set(k2(v)) for k, v in known.items()}
    return s1, s2


def first_source(keys, sets):
    """First source (KNOWN_ORDER) whose set holds each key, or ''."""
    out = []
    for k in keys:
        for n in KNOWN_ORDER:
            if k in sets[n]:
                out.append(n); break
        else:
            out.append("")
    return out
