#!/usr/bin/env python3
"""r16 dev-set picker: a fixed unseen-vendor DEV set held back from round 16 training (stdlib only, deterministic).
Never trained on, never the ship gate (exam #8 is the gate); used only to compare small round 16 test runs.
Pool = master-sheet vendors (vendor_id == vendor_key) that appear in no r15 pick, not in R13, not in any exclusion list.
Run:  python3 r16/pick_dev.py            (seed 16; writes data/r16/dev/{dev-vendors.csv,dev-ops.csv.gz,pick-report.json})
"""
import argparse, io, collections, csv, gzip, hashlib, json, os, random, re

csv.field_size_limit(10**9)
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
D = os.path.join(REPO, "data")
MASTER = os.path.join(D, "r15", "master", "ops-r15-master.csv.gz")
PICKS = os.path.join(D, "r15", "picks", "pick-200000-1.csv.gz")
R13 = os.path.join(D, "round13", "vendors-r13-seen.txt")
EX7 = os.path.join(D, "r15", "exam7-exclusions.json")
EXKEYS = os.path.join(D, "r15", "exclusion-keys.txt")
FLAGGED = os.path.join(D, "r15", "rwxmap-flagged.txt")
OUT = os.path.join(D, "r16", "dev")

# exam #8 freeze (rwxmap 2026-11-20): brand aliases (whole labels), domains (whole label sequences), repos (owner/name)
EXAM8 = {
    "gitbook": {"labels": ["gitbook"], "domains": ["api.gitbook.com", "gitbook.com"], "repos": []},
    "baserow": {"labels": ["baserow"], "domains": ["api.baserow.io", "baserow.io"], "repos": []},
    "looker": {"labels": ["looker", "looker-open-source"], "domains": ["looker.com"], "repos": ["looker-open-source/sdk-codegen"]},
    "wekan": {"labels": ["wekan"], "domains": ["wekan.github.io"], "repos": ["wekan/wekan"]},
    "shortcut": {"labels": ["shortcut", "clubhouse"], "domains": ["shortcut.com", "developer.shortcut.com", "api.app.shortcut.com", "clubhouse.io"], "repos": []},
    "bitrise": {"labels": ["bitrise"], "domains": ["bitrise.io", "api-docs.bitrise.io", "api.bitrise.io"], "repos": []},
}
VFIELDS = ["servers_domains", "contact_domain", "logo_domain", "spec_title", "title_norm", "repo_owner", "repo_url"]
SCAN = VFIELDS + ["vendor_key", "repo", "repo_name", "servers", "contact_url", "website", "publisher", "product", "file_path", "folder"]
CLOUD = {"alibaba", "huawei"}
ACCESS = re.compile(r"\b(access|permissions?|polic(?:y|ies)|roles?|grants?|acls?|rbac|privileges?|entitlements?)\b")
SPLIT = re.compile(r"[^a-z0-9._\-/]+")


def fam(s):
    return "github" if s == "github" else "swaggerhub" if s == "swaggerhub" else "cloud" if s in CLOUD else "catalogues"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def labels_of(text):
    """whole domain labels / path parts / hyphen-underscore parts, lowercase."""
    out = set()
    for tok in SPLIT.split(text.lower()):
        for part in re.split(r"[./]", tok):
            if part:
                out.add(part)
                out.update(x for x in re.split(r"[-_]", part) if x)
    return out


def seq_in(text, seq):
    """seq of labels occurs contiguously in some dotted token of text"""
    n = len(seq)
    for tok in SPLIT.split(text.lower()):
        parts = [p for p in re.split(r"[./]", tok) if p]
        for i in range(len(parts) - n + 1):
            if parts[i:i + n] == seq:
                return True
    return False


def hits8(row):
    """exam #8 vendors this op matches: whole label / whole domain / whole repo, plus a substring audit (strict=False)."""
    whole, sub = set(), set()
    for f in SCAN:
        t = row.get(f, "") or ""
        if not t:
            continue
        lab = labels_of(t)
        low = t.lower()
        for v, e in EXAM8.items():
            if any(l in lab for l in e["labels"]) or any(seq_in(t, d.split(".")) for d in e["domains"]) \
               or any(r in low for r in e["repos"]):
                whole.add(v)
            elif any(l in low.replace("-", "").replace("_", "").replace(" ", "") for l in e["labels"]):
                sub.add(v)
    return whole, sub


def regdom(d):
    p = d.split(".")
    if len(p) >= 3 and p[-2] in {"co", "com", "org", "net", "gov", "ac"} and len(p[-1]) == 2:
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=16)
    ap.add_argument("--target-ops", type=int, default=4000)
    ap.add_argument("--cap", type=int, default=30)
    ap.add_argument("--min-ops", type=int, default=12, help="min eligible ops for a vendor to be a candidate")
    ap.add_argument("--cands", type=int, default=300, help="seeded candidate draws; the best mix wins")
    ap.add_argument("--langs", default="en,other", help="allowed lang values (master lang column); r15 used en only")
    ap.add_argument("--allow-rpc", action="store_true", help="keep RPC-style ops (r15 dropped them)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    # matcher self-test: whole labels / domains / repos hit, look-alikes only reach the substring audit
    assert hits8({"servers_domains": "api.gitbook.com"})[0] == {"gitbook"}
    assert hits8({"repo": "looker-open-source/sdk-codegen"})[0] == {"looker"}
    assert hits8({"vendor_key": "wekan.github.io"})[0] == {"wekan"}
    assert hits8({"title_norm": "shortcut"})[0] == {"shortcut"} and hits8({"contact_domain": "clubhouse.io"})[0] == {"shortcut"}
    assert hits8({"spec_title": "Bitrise API"})[0] == {"bitrise"} and hits8({"servers_domains": "api.baserow.io"})[0] == {"baserow"}
    assert hits8({"spec_title": "Keyboard shortcut"})[0] == {"shortcut"} and hits8({"title_norm": "keyboardshortcuts"}) == (set(), {"shortcut"})
    os.makedirs(a.out, exist_ok=True)

    pick_vendors, pick_ops, pick_specs = set(), set(), set()
    with gzip.open(PICKS, "rt", newline="") as f:
        for r in csv.DictReader(f):
            pick_vendors.add(r["vendor_key"]); pick_ops.add(r["op_id"]); pick_specs.add(r["spec_sha256"])
    r13 = {l.strip() for l in open(R13) if l.strip()}
    exkeys = {l.strip() for l in open(EXKEYS) if l.strip()}
    flagged = {l.strip() for l in open(FLAGGED) if l.strip()}
    ex7 = json.load(open(EX7))
    ex7_labels = {x.lower() for e in ex7["exam"].values() for x in e["aliases"]}
    ex7_repos = {x.lower() for e in ex7["exam"].values() for x in e["repos"]}

    # ---- stream the master, keep only never-used vendors
    rows, hdr, total = [], None, 0
    with gzip.open(MASTER, "rt", newline="") as f:
        rd = csv.DictReader(f)
        hdr = rd.fieldnames
        for r in rd:
            total += 1
            if r["vendor_key"] not in pick_vendors:
                rows.append(r)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["vendor_key"]].append(r)
    rep = {"seed": a.seed, "master_rows": total, "r15_pick_vendors": len(pick_vendors),
           "unused_rows": total - 200000, "pool_ops": len(rows), "pool_vendors": len(by)}
    # how "never used" was decided: three independent exact-key checks on the pool, all must be 0
    rep["never_used_check"] = {
        "rule": "vendor_key not in r15 picks (pick-200000-1.csv.gz vendor_key); also not in R13 seen list, exclusion-keys.txt, as exact keys",
        "pool_vendors_in_r13_seen_exact": sum(v in r13 for v in by),
        "pool_vendors_in_exclusion_keys_exact": sum(v in exkeys for v in by),
        "pool_ops_in_r15_picks_by_op_id": sum(r["op_id"] in pick_ops for r in rows),
    }
    assert all(v == 0 for k, v in rep["never_used_check"].items() if k.startswith("pool_"))

    def fields(rs, k):
        s = set()
        for r in rs:
            for x in re.split(r"[|;,]", r[k]):
                if x.strip():
                    s.add(x.strip())
        return sorted(s)

    # ---- vendor-level drops (cheapest-first, each vendor counted once at its first reason)
    drops = collections.OrderedDict((k, []) for k in ["exam8", "exam8_substring_audit", "exam7_alias", "flagged_spec",
                                                      "spec_in_r15_pick", "r13_token", "r15_pick_registrable_domain", "exclusion_keys_registrable_domain"])
    pick_dom = {regdom(v) for v in pick_vendors if "." in v and ":" not in v}
    ek_dom = {regdom(v) for v in exkeys if "." in v and ":" not in v}
    r13_tokens = r13
    ok = {}
    detail8 = collections.defaultdict(lambda: {"vendors": 0, "ops": 0})
    for v, rs in sorted(by.items()):
        w, s = set(), set()
        for r in rs:
            a1, b1 = hits8(r)
            w |= a1; s |= b1
        if w:
            drops["exam8"].append(v)
            for x in w:
                detail8[x]["vendors"] += 1; detail8[x]["ops"] += len(rs)
            continue
        if s:
            drops["exam8_substring_audit"].append((v, sorted(s))); continue
        lab = set()
        for r in rs:
            for f in SCAN:
                lab |= labels_of(r.get(f, "") or "")
        t7 = set()
        for r in rs:
            t7 |= {r["repo"].lower(), r["repo_url"].lower()}
        if lab & ex7_labels or any(x and any(e in t for e in ex7_repos) for t in t7 for x in [t]):
            drops["exam7_alias"].append(v); continue
        if any(r["spec_sha256"] in flagged for r in rs):
            drops["flagged_spec"].append(v); continue
        if any(r["spec_sha256"] in pick_specs for r in rs):
            drops["spec_in_r15_pick"].append(v); continue
        kind = rs[0]["vendor_kind"]
        if kind == "domain":
            vl = set(v.lower().split("."))
            if vl & r13_tokens:
                drops["r13_token"].append(v); continue
            if regdom(v.lower()) in pick_dom:
                drops["r15_pick_registrable_domain"].append(v); continue
            if regdom(v.lower()) in ek_dom:
                drops["exclusion_keys_registrable_domain"].append(v); continue
        elif kind == "title":
            if rs[0]["title_norm"] in r13_tokens:
                drops["r13_token"].append(v); continue
        ok[v] = rs
    rep["exam8_dropped_by_rule"] = {k: dict(x) for k, x in detail8.items()}
    rep["vendor_drops"] = {k: len(x) for k, x in drops.items()}
    rep["vendor_drops_ops"] = {k: sum(len(by[x[0] if isinstance(x, tuple) else x]) for x in xs) for k, xs in drops.items()}
    rep["exam8_dropped_vendor_keys"] = drops["exam8"]
    rep["exam8_substring_audit_vendor_keys"] = [list(x) for x in drops["exam8_substring_audit"]]
    rep["pool_after_drops"] = {"vendors": len(ok), "ops": sum(len(x) for x in ok.values())}

    # ---- eligibility (same defaults as r15 picker) per op
    langs = set(a.langs.split(","))

    def eligible(r):
        fl = r["flags"] or ""
        return (r["lang"] in langs and r["has_text"] == "True" and not (r["dup_of"] or "")
                and "junk_domain" not in fl and (a.allow_rpc or not re.search(r"(^|;)rpc(;|$)", fl)) and "non_http_method" not in fl)
    cand = {}
    for v, rs in ok.items():
        e = [r for r in rs if eligible(r)]
        if len(e) >= a.min_ops:
            cand[v] = sorted(e, key=lambda r: r["op_id"])
    rep["candidate_vendors"] = {"vendors": len(cand), "ops": sum(len(x) for x in cand.values()), "min_eligible_ops": a.min_ops}

    def vfam(rs):
        c = collections.Counter(fam(r["source"]) for r in rs)
        return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    vf = {v: vfam(rs) for v, rs in cand.items()}

    def kw(r):
        t = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", " ".join([r["path"], r["operationId"], r["summary"]]))
        return bool(ACCESS.search(re.sub(r"[^a-z0-9]+", " ", t.lower())))

    def mix(rs, key):
        c = collections.Counter(key(r) for r in rs)
        n = sum(c.values()) or 1
        return {k: round(c[k] / n, 4) for k in sorted(c)}
    pool_all = [r for rs in by.values() for r in rs]
    full = {"method_mix": mix(pool_all, lambda r: r["method_norm"]), "source_mix": mix(pool_all, lambda r: fam(r["source"])),
            "access_kw_ops": sum(kw(r) for r in pool_all), "access_kw_share": round(sum(kw(r) for r in pool_all) / len(pool_all), 4)}
    rep["pool_118812_full"] = full
    # eligibility matrix on the pool after drops (why the full pool is not directly usable)
    rep["pool_eligibility_matrix"] = {
        "lang_counts": dict(collections.Counter(r["lang"] for rs in ok.values() for r in rs)),
        "dup_ops": sum(1 for rs in ok.values() for r in rs if r["dup_of"]),
        "no_text_ops": sum(1 for rs in ok.values() for r in rs if r["has_text"] != "True"),
        "rpc_ops": sum(1 for rs in ok.values() for r in rs if "rpc" in r["flags"].split(";")),
        "junk_domain_ops": sum(1 for rs in ok.values() for r in rs if "junk_domain" in r["flags"]),
        "en_text_nodup_nojunk_nonrpc_ops(r15 defaults)": sum(1 for rs in ok.values() for r in rs if r["lang"] == "en" and r["has_text"] == "True" and not r["dup_of"] and "junk_domain" not in r["flags"] and "rpc" not in r["flags"].split(";")),
        "en_text_nodup_nojunk_incl_rpc_ops": sum(1 for rs in ok.values() for r in rs if r["lang"] == "en" and r["has_text"] == "True" and not r["dup_of"] and "junk_domain" not in r["flags"]),
        "en_text_nodup_nojunk_incl_rpc_sources": dict(collections.Counter(r["source"] for rs in ok.values() for r in rs if r["lang"] == "en" and r["has_text"] == "True" and not r["dup_of"] and "junk_domain" not in r["flags"])),
    }
    cand_rows = [r for v in cand for r in cand[v]]
    ref_m = mix(cand_rows, lambda r: r["method_norm"])
    ref_s = mix(cand_rows, lambda r: fam(r["source"]))
    ref_kw = sum(kw(r) for r in cand_rows) / len(cand_rows)
    rep["eligible_pool_reference"] = {"rule": "lang in %s, has_text, not dup, not junk_domain, %s, vendors with >= %d such ops" % (sorted(langs), "rpc kept" if a.allow_rpc else "not rpc", a.min_ops),
                                      "ops": len(cand_rows), "vendors": len(cand), "method_mix": ref_m, "source_mix": ref_s, "access_kw_ops": sum(kw(r) for r in cand_rows), "access_kw_share": round(ref_kw, 4)}

    quota = {f: a.target_ops * ref_s.get(f, 0) for f in ["github", "swaggerhub", "cloud", "catalogues"]}

    def draw(rng):
        sel = []
        for f, q in quota.items():
            vs = sorted(v for v in cand if vf[v] == f)
            rng.shuffle(vs)
            tot = 0
            for v in vs:
                if tot >= q and sel_f(sel, f, vf) >= 1:
                    break
                ops = cand[v] if len(cand[v]) <= a.cap else rng.sample(cand[v], a.cap)
                sel.append((v, sorted(ops, key=lambda r: r["op_id"]))); tot += len(ops)
        return sel

    def sel_f(sel, f, vf_):
        return sum(1 for v, _ in sel if vf_[v] == f)

    def score(sel):
        ops = [r for _, o in sel for r in o]
        m = mix(ops, lambda r: r["method_norm"])
        d = sum(abs(m.get(k, 0) - ref_m.get(k, 0)) for k in set(m) | set(ref_m))
        d += 0.5 * abs(sum(kw(r) for r in ops) / len(ops) - ref_kw)
        d += abs(len(sel) - 175) / 400.0  # soft pull toward ~175 vendors
        return d
    best = None
    for i in range(a.cands):
        sel = draw(random.Random("%d-%d" % (a.seed, i)))
        s = score(sel)
        if best is None or s < best[0]:
            best = (s, i, sel)
    s, bi, sel = best
    sel.sort(key=lambda t: t[0])
    dev_ops = [r for _, o in sel for r in o]

    # ---- hard asserts: no overlap with anything used or excluded
    dv = {v for v, _ in sel}
    assert not dv & pick_vendors and not dv & r13 and not dv & exkeys
    assert not {r["op_id"] for r in dev_ops} & pick_ops
    assert not {r["spec_sha256"] for r in dev_ops} & (flagged | pick_specs)
    for r in dev_ops:
        assert hits8(r) == (set(), set()), r["op_id"]
        assert not (labels_of(r["vendor_key"]) & ex7_labels)
    assert all(len(o) <= a.cap for _, o in sel)

    # ---- outputs
    with open(os.path.join(a.out, "dev-ops.csv.gz"), "wb") as raw, \
         gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=6) as gz, \
         io.TextIOWrapper(gz, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr, lineterminator="\n")
        w.writeheader()
        for r in dev_ops:
            w.writerow(r)
    vcols = ["vendor_key", "vendor_kind", "source_family", "sources", "pool_ops", "dev_ops"] + \
            ["servers_domains", "contact_domains", "logo_domains", "spec_titles", "title_norms", "repo_owners", "repo_urls"]
    with open(os.path.join(a.out, "dev-vendors.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(vcols)
        for v, o in sel:
            rs = by[v]
            w.writerow([v, rs[0]["vendor_kind"], vf[v], "|".join(sorted({r["source"] for r in rs})), len(rs), len(o)] +
                       ["|".join(fields(rs, k)) for k in VFIELDS])
    rep["dev"] = {"vendors": len(sel), "ops": len(dev_ops), "cap": a.cap, "chosen_candidate": bi, "candidates_drawn": a.cands,
                  "target_ops": a.target_ops, "min_eligible_ops": a.min_ops,
                  "method_mix": mix(dev_ops, lambda r: r["method_norm"]), "source_mix": mix(dev_ops, lambda r: fam(r["source"])),
                  "raw_source_counts": dict(collections.Counter(r["source"] for r in dev_ops)),
                  "vendors_by_family": dict(collections.Counter(vf[v] for v in dv)), "vendors_by_kind": dict(collections.Counter(by[v][0]["vendor_kind"] for v in dv)),
                  "ops_per_vendor_min_median_max": [min(len(o) for _, o in sel), sorted(len(o) for _, o in sel)[len(sel) // 2], max(len(o) for _, o in sel)],
                  "method_mix_L1_vs_eligible_pool": round(sum(abs(mix(dev_ops, lambda r: r["method_norm"]).get(k, 0) - ref_m.get(k, 0)) for k in ref_m), 4),
                  "method_mix_L1_vs_full_pool": round(sum(abs(mix(dev_ops, lambda r: r["method_norm"]).get(k, 0) - full["method_mix"].get(k, 0)) for k in full["method_mix"]), 4),
                  "lang_counts": dict(collections.Counter(r["lang"] for r in dev_ops)),
                  "access_kw_ops": sum(kw(r) for r in dev_ops), "access_kw_share": round(sum(kw(r) for r in dev_ops) / len(dev_ops), 4),
                  "access_kw_vendors": len({r["vendor_key"] for r in dev_ops if kw(r)}),
                  "access_kw_note": "word match (camelCase split) on path+operationId+summary: access|permission(s)|policy/policies|role(s)|grant(s)|acl(s)|rbac|privilege(s)|entitlement(s)"}
    rep["asserts_passed"] = ["no dev vendor_key in r15 picks / R13 seen / exclusion-keys", "no dev op_id in r15 picks",
                             "no dev spec_sha256 in rwxmap-flagged or r15 picks", "no exam #8 hit (whole label/domain/repo and substring) on any scanned field",
                             "no exam #7 alias label on vendor_key", "cap respected"]
    rep["inputs_sha256"] = {os.path.relpath(p, REPO): sha(p) for p in [MASTER, PICKS, R13, EX7, EXKEYS, FLAGGED]}
    rep["outputs_sha256"] = {n: sha(os.path.join(a.out, n)) for n in ["dev-vendors.csv", "dev-ops.csv.gz"]}
    json.dump(rep, open(os.path.join(a.out, "pick-report.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: rep[k] for k in ["pool_ops", "pool_vendors", "vendor_drops", "pool_after_drops", "candidate_vendors", "dev"]}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
