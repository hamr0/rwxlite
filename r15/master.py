#!/usr/bin/env python3
"""r15 master sheet: one clean table of all round-15 operations (table building only, no labelling/model).
Inputs  data/r15/ops-r15{,-swaggerhub,-catalogues,-cloud}.parquet (+ catalogues-extra sidecar joined on op_id).
Outputs data/r15/master/ops-r15-master.{csv.gz,parquet}, vendors-r15-master.csv, master-report.json,
        dropped-rwxmap.csv.gz (only when data/r15/rwxmap-flagged.txt exists: one spec_sha256 per line).
Hard drops: empty path / no method, exact duplicates, rwxmap-flagged specs.  Everything else is TAGGED (flags column).
Re-run (minutes):  nice -n 19 ionice -c3 python3 r15/master.py
"""
import html, json, os, re, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
D = os.path.join(REPO, "data", "r15")
OUT = os.path.join(D, "master")
FLAGGED = os.path.join(D, "rwxmap-flagged.txt")
INPUTS = ["ops-r15", "ops-r15-swaggerhub", "ops-r15-catalogues", "ops-r15-cloud"]
TEXT_CAP = 1500
SRC_PRIORITY = {"catalogues": 0, "cloud": 1, "github": 2, "swaggerhub": 3}  # ties in dedupe: lower wins
HTTP_OK = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "QUERY"}
HUGE_SPEC_OPS = 300  # spec reaches the per-vendor cap: truncated / generated mega-spec

# ---- junk domains -------------------------------------------------------------------------------
JUNK_DOMAINS = {"126.com", "163.com", "qq.com", "gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "live.com",
                "icloud.com", "protonmail.com", "foxmail.com", "sina.com", "sohu.com", "yeah.net", "msn.com",
                "aol.com", "gmx.com", "gmx.de", "web.de", "mail.ru", "yandex.ru", "rambler.ru", "bk.ru", "list.ru",
                "inbox.ru", "naver.com", "daum.net", "libero.it", "orange.fr", "free.fr", "wp.pl", "o2.pl",
                "localhost", "example.com", "example.org", "example.net", "example", "your-domain.com",
                "yourdomain.com", "domain.com", "mydomain.com", "test.com", "foo.com", "bar.com", "sample.com"}
JUNK_PATTERNS = re.compile(
    r"(^|\.)(yahoo|hotmail|outlook|live)\.[a-z.]+$|\.(local|test|invalid|localhost|example|internal|localdomain)$|"
    r"^(\d{1,3}\.){3}\d{1,3}$|your[-_]?domain|your[-_]?company|your[-_]?api|\{host\}|\{\{|^host$|^hostname$|"
    r"^api\.example|example\.(com|org|net)$|^(my|the)?[-_]?(host|server|domain)\.(com|org|net)$|^x{3,}\.")


def junk_domain(v):
    if not v:
        return False
    v = v.lower()
    return v in JUNK_DOMAINS or bool(JUNK_PATTERNS.search(v)) or ids.is_generic_domain(v)


# ---- text cleaning ------------------------------------------------------------------------------
_RE = [
    (re.compile(r"<[^>]{0,200}>"), " "),
    (re.compile(r"```.*?```", re.S), " "),
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"https?://\S+"), " "),
    (re.compile(r"(^|\s)#{1,6}\s*"), " "),
    (re.compile(r"[*_`~>|]{1,}"), " "),
]
_WS = re.compile(r"\s+")


def clean_text(s):
    if not s:
        return ""
    s = html.unescape(s)
    for rx, rep in _RE:
        s = rx.sub(rep, s)
    return _WS.sub(" ", s).strip()


def make_text(summ, desc):
    a, b = clean_text(summ), clean_text(desc)
    if a and b and (b.lower().startswith(a.lower().rstrip(". "))):
        t = b
    else:
        t = (a + (". " if a and b and a[-1] not in ".!?:;" else " " if a and b else "") + b).strip()
    return t[:TEXT_CAP]


# ---- language (cheap script ratio + stopwords) ------------------------------------------------------
EN_SW = set("the a an of to and or in on for with is are be this that from by as at it its if not no returns return get "
            "gets set sets create creates update updates delete deletes list lists retrieve retrieves all given "
            "specified id user users data new existing used use will can".split())
OT_SW = set("de la le les des du un une et en pour par est sont que qui dans sur avec el los las del por para con "
            "una es se su um uma não nao os as dos das ou ao der die das und ein eine mit von zu den ist nicht "
            "il lo gli per di che non sono della degli het een van voor niet yang dan untuk dengan dari atau "
            "ini pada kepada".split())
_TOK = re.compile(r"[a-zA-ZÀ-ɏ]+")


def lang_signal(t):
    """returns (lang, strong).  lang in en|zh|ru|other; strong=False when only weak latin evidence."""
    if not t:
        return "", False
    cjk = ru = lat = 0
    for ch in t:
        o = ord(ch)
        if 0x4e00 <= o <= 0x9fff or 0x3400 <= o <= 0x4dbf:
            cjk += 1
        elif 0x400 <= o <= 0x4ff:
            ru += 1
        elif (0x41 <= o <= 0x5a) or (0x61 <= o <= 0x7a) or (0xc0 <= o <= 0x24f):
            lat += 1
        elif 0x3040 <= o <= 0x30ff or 0xac00 <= o <= 0xd7af or 0x600 <= o <= 0x6ff or 0x0e00 <= o <= 0x0e7f or 0x0900 <= o <= 0x097f:
            lat -= 0  # other scripts counted below
    tot_alpha = sum(1 for ch in t if ch.isalpha())
    if tot_alpha == 0:
        return "", False
    if cjk / tot_alpha > 0.15:
        return "zh", True
    if ru / tot_alpha > 0.3:
        return "ru", True
    if lat / tot_alpha < 0.6:
        return "other", True
    toks = [w.lower() for w in _TOK.findall(t)]
    en = sum(w in EN_SW for w in toks)
    ot = sum(w in OT_SW for w in toks)
    accents = sum(1 for ch in t if 0xc0 <= ord(ch) <= 0x24f)
    if ot >= 2 and ot > en:
        return "other", True
    if accents >= 2 and en == 0:
        return "other", True
    if en >= 1:
        return "en", True
    return "en", False


# ---- junk text classes (tags found by reading rows) ------------------------------------------------------
LOREM = re.compile(r"lorem ipsum|dolor sit amet|consectetur adipiscing", re.I)
PLACEHOLDER_TEXT = re.compile(
    r"^(string|description|summary|todo|tbd|n/?a|none|null|test|testing|asdf+|foo|bar|hello( world)?|"
    r"add (a )?description|no description( provided)?|description here|description goes here|"
    r"your description|sample|example|default|operation|undefined|xxx+|\.+|-+|/)\.?$", re.I)
AUTO_OPID = re.compile(r"^(?:[a-z]+_)?[A-Za-z0-9]+_[a-z0-9_]*_(get|post|put|patch|delete|head|options)$|"
                       r"^(get|post|put|patch|delete|head|options)[_-][a-z0-9_/-]+$|"
                       r"^(get|post|put|patch|delete)[A-Z][A-Za-z0-9]*(Using|By)(GET|POST|PUT|PATCH|DELETE)\d*$|"
                       r"^[A-Za-z0-9]+Controller_[A-Za-z0-9]+$|^operation[_-]?\d+$|^[A-Za-z]+_[A-Za-z0-9]+_\d+$|"
                       r"^(get|post|put|patch|delete)\w*Using(GET|POST|PUT|PATCH|DELETE)\d*$")
TEST_SEG = re.compile(r"^(/(api|rest|v\d+(\.\d+)*))*/(test|tests|testing|dummy|foo|bar|foobar|hello|helloworld|sample|samples|"
                      r"example|examples|mock|echo|demo|todo|todos)(/|$)", re.I)


def build_flags(df):
    f = pd.DataFrame(index=df.index)
    f["junk_domain"] = df["_junk"]
    f["no_text"] = ~df["has_text"]
    f["rpc"] = (df["api_style"] == "rpc") if "api_style" in df else False
    f["non_http_method"] = ~df["method_norm"].isin(HTTP_OK)
    f["huge_spec"] = df["_spec_ops"] >= HUGE_SPEC_OPS
    p = df["path"]
    f["odd_path"] = ((~p.str.startswith("/")) & ~f["rpc"] & (df["source"] != "huawei")) | p.str.contains(r"\s|\$ref|^https?:|\{\{", regex=True) \
        | (p.str.len() > 200) | (p.str.count(r"\{") != p.str.count(r"\}"))
    tc = df["text_clean"]
    f["lorem"] = tc.str.contains(LOREM)
    ph = tc.str.fullmatch(PLACEHOLDER_TEXT) | (tc.str.len() < 2) & df["has_text"]
    f["placeholder_text"] = ph & ~f["no_text"] & (df["operationId"].str.len() == 0) | (tc.str.fullmatch(PLACEHOLDER_TEXT) & (df["summary"].str.len() < 12))
    f["autogen_opid_only"] = (tc.str.len() == 0) & df["operationId"].str.match(AUTO_OPID)
    f["test_endpoint"] = df["path_norm"].str.match(TEST_SEG)
    names = ["junk_domain", "no_text", "rpc", "non_http_method", "huge_spec", "odd_path", "lorem", "placeholder_text",
             "autogen_opid_only", "test_endpoint"]
    arr = f[names].to_numpy()
    return pd.Series([";".join(n for n, b in zip(names, row) if b) for row in arr], index=df.index), f


# ---- specs: near-duplicate grouping (MinHash + LSH bands, exact Jaccard verification) ---------------------------
def spec_groups(df, min_ops=5, thr=0.8, nperm=64, bands=16):
    """df has spec_sha256, method_norm, path_norm.  Returns dict sha -> group index (only specs in a multi-spec group)."""
    key = pd.util.hash_pandas_object(df["method_norm"] + " " + df["path_norm"], index=False).to_numpy(dtype=np.uint64)
    sp = df["spec_sha256"].to_numpy()
    codes, uniq = pd.factorize(sp)
    order = np.argsort(codes, kind="stable")
    codes_s, key_s = codes[order], key[order]
    bounds = np.flatnonzero(np.diff(codes_s)) + 1
    sets = [np.unique(k) for k in np.split(key_s, bounds)]  # indexed by code (sorted codes 0..n-1)
    keep = [i for i, s in enumerate(sets) if len(s) >= min_ops]
    # collapse identical sets
    by_sig = {}
    for i in keep:
        by_sig.setdefault(hash(sets[i].tobytes()), []).append(i)
    reps = [v[0] for v in by_sig.values()]
    rng = np.random.default_rng(12345)
    A = rng.integers(1, 2**61 - 1, size=nperm, dtype=np.uint64) | np.uint64(1)
    B = rng.integers(0, 2**61 - 1, size=nperm, dtype=np.uint64)
    sig = np.empty((len(reps), nperm), dtype=np.uint64)
    for j, i in enumerate(reps):
        sig[j] = (sets[i][:, None] * A[None, :] + B[None, :]).min(axis=0)  # wraps mod 2^64: fine as a hash family
    rows = bands and nperm // bands
    parent = list(range(len(reps)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for b in range(bands):
        h = np.array([hash(r.tobytes()) for r in sig[:, b * rows:(b + 1) * rows]], dtype=np.int64)
        buckets = {}
        for j, hv in enumerate(h):
            buckets.setdefault(int(hv), []).append(j)
        for mem in buckets.values():
            if len(mem) < 2:
                continue
            if len(mem) > 300:  # giant bucket (generic path sets): compare neighbours only, keeps cost linear
                pairs = [(mem[k], mem[k + 1]) for k in range(len(mem) - 1)]
            else:
                pairs = [(mem[x], mem[y]) for x in range(len(mem)) for y in range(x + 1, len(mem))]
            for a, c in pairs:
                ra, rc = find(a), find(c)
                if ra == rc:
                    continue
                sa, sc = sets[reps[a]], sets[reps[c]]
                inter = np.intersect1d(sa, sc, assume_unique=True).size
                if inter / (len(sa) + len(sc) - inter) >= thr:
                    parent[ra] = rc
    comp = {}
    for j in range(len(reps)):
        comp.setdefault(find(j), []).append(j)
    sig_members = {hash(sets[v[0]].tobytes()): v for v in by_sig.values()}
    out = {}
    g = 0
    for members in comp.values():
        shas = []
        for j in members:
            shas.extend(uniq[i] for i in sig_members[hash(sets[reps[j]].tobytes())])
        if len(shas) < 2:
            continue
        for s in shas:
            out[s] = g
        g += 1
    return out


def main():
    t0 = time.time()
    log = lambda *a: print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)
    os.makedirs(OUT, exist_ok=True)
    rep = {}
    frames = []
    for n in INPUTS:
        d = pd.read_parquet(os.path.join(D, n + ".parquet")).astype(str).replace({"nan": "", "None": ""})
        if "source" not in d:
            d["source"] = "github"
        d["_file"] = n
        frames.append(d)
        rep.setdefault("input_rows", {})[n] = len(d)
    df = pd.concat(frames, ignore_index=True)
    # catalogues parquet already carries the sidecar columns (visibility..privacy_url); concat fills the others with ''
    df = df.fillna('')
    for c in ["api_style", "product"]:
        df[c] = df[c].fillna("")
    df = df.drop(columns=[]) if False else df
    orig_cols = [c for c in df.columns if c != "_file"]
    log("loaded", len(df))

    # ---- hard drops 1: empty path / no method / exact duplicates
    df["method_norm"] = df["method"].str.strip().str.upper()
    bad = (df["path"].str.strip() == "") | (df["method_norm"] == "")
    rep["dropped_empty_path_or_method"] = int(bad.sum())
    df = df[~bad]
    before = len(df)
    df = df.drop_duplicates(subset=orig_cols)
    df = df.drop_duplicates(subset=["spec_sha256", "method_norm", "path"])
    rep["dropped_exact_duplicates"] = before - len(df)
    # ---- hard drops 2: rwxmap-flagged specs (re-runnable)
    rep["rwxmap_flagged_file"] = os.path.exists(FLAGGED)
    dropped_path = os.path.join(OUT, "dropped-rwxmap.csv.gz")
    if rep["rwxmap_flagged_file"]:
        flagged = {l.strip().split(",")[0].split()[0] for l in open(FLAGGED) if l.strip() and not l.startswith("#")}
        m = df["spec_sha256"].isin(flagged)
        pf = {}
        for fn in INPUTS:
            a = df[df["_file"] == fn]
            b = a[a["spec_sha256"].isin(flagged)]
            pf[fn] = {"specs_before": int(a["spec_sha256"].nunique()), "ops_before": len(a),
                      "specs_dropped": int(b["spec_sha256"].nunique()), "ops_dropped": len(b),
                      "specs_after": int(a.loc[~a["spec_sha256"].isin(flagged), "spec_sha256"].nunique()),
                      "ops_after": len(a) - len(b)}
        rep["rwxmap_drop_per_file"] = pf
        rep["rwxmap_drop_distinct_specs_hit"] = int(df.loc[m, "spec_sha256"].nunique())
        rep["rwxmap_drop_total_ops"] = int(m.sum())
        rep["rwxmap_flagged_not_found"] = len(flagged - set(df["spec_sha256"]))
        df[m].drop(columns=["_file"]).to_csv(dropped_path, index=False, compression="gzip")
        df = df[~m]
        rep["dropped_rwxmap_flagged_rows"] = int(m.sum())
        rep["rwxmap_flagged_specs_listed"] = len(flagged)
    df = df.reset_index(drop=True)
    log("after hard drops", len(df))

    # ---- derived columns
    df["path_norm"] = (df["path"].str.replace(r"\{[^}]*\}", "{}", regex=True).str.lower()
                       .str.rstrip("/").replace("", "/"))
    vk = df["vendor_key"]
    df["vendor_id"] = vk
    kind = np.where(vk.str.startswith("title:"), "title", np.where(vk.str.startswith("owner:"), "owner",
                    np.where(vk.str.startswith(("aliyun:", "huaweicloud:")), "product", "domain")))
    df["vendor_kind"] = kind
    dom = vk.where(df["vendor_kind"] == "domain", "")
    df["_junk"] = dom.map(junk_domain)
    df["text_clean"] = [make_text(a, b) for a, b in zip(df["summary"], df["description"])]
    df["has_text"] = (df["summary"].str.strip() != "") | (df["description"].str.strip() != "") | (df["operationId"].str.strip() != "")
    log("text cleaned")
    sig = [lang_signal(t if t else o) for t, o in zip(df["text_clean"], df["operationId"])]
    df["_l"] = [s[0] for s in sig]
    df["_strong"] = [s[1] for s in sig]
    # weak latin evidence (short strings) inherits the spec's majority among strong ops
    strong = df[df["_strong"] & (df["_l"] != "")]
    maj = strong.groupby("spec_sha256")["_l"].agg(lambda s: s.value_counts().index[0])
    sm = df["spec_sha256"].map(maj)
    df["lang"] = np.where(df["_strong"], df["_l"], np.where((df["_l"] == "en") & sm.notna(), sm, np.where(df["_l"] == "", "other", df["_l"])))
    df["lang"] = df["lang"].replace("", "other")
    log("lang done")
    df["_spec_ops"] = df.groupby("spec_sha256")["op_id"].transform("size")

    # ---- spec near-duplicate groups (computed on all rows, before cross-source dedupe)
    sg = spec_groups(df)
    log("spec groups", len(set(sg.values())), "specs in groups", len(sg))
    stats = df.groupby("spec_sha256").agg(tl=("text_clean", lambda s: s.str.len().sum()), src=("source", "first"))
    stats["prio"] = stats["src"].map(lambda s: SRC_PRIORITY[src_family(s)])
    spec_grp = pd.Series(sg)
    primary = {}
    st = stats.loc[stats.index.intersection(spec_grp.index)].copy()
    st["g"] = spec_grp.loc[st.index]
    st.index.name = "spec_sha256"
    st = st.reset_index().sort_values(["g", "tl", "prio", "spec_sha256"], ascending=[True, False, True, True])
    for g, s in st.groupby("g", sort=False):
        primary[g] = s["spec_sha256"].iloc[0]
    df["spec_group"] = df["spec_sha256"].map(lambda s: f"sg-{sg[s]}" if s in sg else "")
    df["dup_of"] = [("" if (s not in sg or primary[sg[s]] == s) else primary[sg[s]]) for s in df["spec_sha256"]]

    # ---- cross-source dedupe on (vendor_id, method_norm, path_norm)
    df["_fam"] = df["source"].map(src_family)
    df["_prio"] = df["_fam"].map(SRC_PRIORITY)
    df["_tl"] = df["text_clean"].str.len()
    df["_isdup"] = (df["dup_of"] != "").astype(int)
    df = df.sort_values(["vendor_id", "method_norm", "path_norm", "_isdup", "_tl", "_prio", "op_id"],
                        ascending=[True, True, True, True, False, True, True], kind="stable").reset_index(drop=True)
    k = ["vendor_id", "method_norm", "path_norm"]
    gsize = df.groupby(k, sort=False)["op_id"].transform("size")
    df["also_in"] = ""
    multi = df[gsize > 1]
    ai = multi.groupby(k, sort=False)["source"].agg(list)
    first_src = multi.groupby(k, sort=False)["source"].first()
    also = {key: "|".join(sorted({x for x in lst if x != first_src[key]})) for key, lst in ai.items()}
    keep_mask = ~df.duplicated(subset=k, keep="first")
    removed = int((~keep_mask).sum())
    df = df[keep_mask].copy()
    if also:
        idx = pd.MultiIndex.from_frame(df[k])
        df["also_in"] = pd.Series(idx.map(lambda t: also.get(t, "")), index=df.index).fillna("")
    rep["cross_source_dedupe_removed"] = removed
    log("deduped, removed", removed, "now", len(df))

    # ---- flags (spec_ops recomputed on the final table)
    df["_spec_ops"] = df.groupby("spec_sha256")["op_id"].transform("size")
    df["flags"], fl = build_flags(df)
    df["lang"] = df["lang"]

    new_cols = ["source", "method_norm", "path_norm", "vendor_id", "vendor_kind", "lang", "has_text", "text_clean", "flags",
                "spec_group", "dup_of", "also_in"]
    cols = [c for c in orig_cols if c != "source"] + new_cols
    out = df[cols].sort_values(["vendor_id", "op_id"]).reset_index(drop=True)
    out.to_parquet(os.path.join(OUT, "ops-r15-master.parquet"), index=False)
    out.to_csv(os.path.join(OUT, "ops-r15-master.csv.gz"), index=False, compression="gzip")
    log("written", len(out))

    # ---- vendors table
    prim = out["dup_of"] == ""
    out["_p"] = prim
    ex = out.groupby("vendor_id")["repo"].first()
    vend = out.groupby("vendor_id").agg(vendor_kind=("vendor_kind", "first"), sources=("source", lambda s: "|".join(sorted(set(s)))),
                                        ops=("op_id", "size"), primary_ops=("_p", "sum"))
    vend["example"] = ex
    vend.reset_index().to_csv(os.path.join(OUT, "vendors-r15-master.csv"), index=False)

    # ---- report
    flag_counts = {c: int(fl[c].loc[out.index.map(lambda _: True) is not None and df.index].sum()) for c in fl.columns} if False else {c: int(v) for c, v in fl.sum().items()}
    rep.update({
        "master_rows": len(out),
        "rows_per_source": out["source"].value_counts().to_dict(),
        "vendors": int(out["vendor_id"].nunique()),
        "vendors_by_kind": vend["vendor_kind"].value_counts().to_dict(),
        "flag_counts": flag_counts,
        "flagged_any_rows": int((out["flags"] != "").sum()),
        "lang_split": out["lang"].value_counts().to_dict(),
        "spec_groups": int(out.loc[out["spec_group"] != "", "spec_group"].nunique()),
        "specs_in_groups": len(sg),
        "dup_rows_marked": int((out["dup_of"] != "").sum()),
        "primary_rows": int(prim.sum()),
        "rows_with_also_in": int((out["also_in"] != "").sum()),
        "dedupe_priority": "catalogues > cloud > github > swaggerhub",
        "seconds": round(time.time() - t0),
    })
    json.dump(rep, open(os.path.join(OUT, "master-report.json"), "w"), indent=1, default=int)
    log(json.dumps(rep, indent=1, default=int))


def src_family(s):
    if s in ("alibaba", "huawei"):
        return "cloud"
    if s in ("github", "swaggerhub"):
        return s
    return "catalogues"


if __name__ == "__main__":
    main()
