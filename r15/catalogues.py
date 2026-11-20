#!/usr/bin/env python3
"""r15 catalogue sources: PowerPlatformConnectors (MIT), wso2/api-specs (Apache-2.0), konfig openapi-examples, activepieces.  QUARANTINED: no labelling.

Reads clones under data/r15/raw/catalogues/, applies the r15 filter rules (reusing r15/filter.py and
r15/extract.py helpers), writes ONLY new files in data/r15/:
  ops-r15-catalogues.parquet / .csv.gz   (csv: exactly the ops-r15.csv.gz columns + `source`)
  ops-r15-catalogues-extra.csv.gz        (op_id, visibility, deprecated, repo_url, folder, publisher, website, privacy_url)
  providers-r15-catalogues.csv, collect-report-catalogues.json
    nice -n 19 ionice -c3 python3 r15/catalogues.py
"""
import glob, hashlib, json, os, re, sys, yaml
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids, extract, filter as flt

D, CAT = flt.D, os.path.join(flt.D, "raw", "catalogues")
OUT_COLS = extract.COLS + ["source"]
ids.GENERIC_HOSTS.update({"azure-api.net", "azure-apim.net", "azure.net"})  # APIM gateway hosts are not a vendor identity
Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
s = extract.s
SRC_ORDER = ["powerplatform-certified", "powerplatform-independent", "powerplatform-custom", "wso2", "konfig", "activepieces"]
PP = {"powerplatform-certified": "certified-connectors", "powerplatform-independent": "independent-publisher-connectors",
      "powerplatform-custom": "custom-connectors"}
REPOS = {"openapi-examples": ("konfig-sdks/openapi-examples", "unknown (no LICENSE file; README badge says MIT)"),
         "activepieces": ("activepieces/activepieces", "MIT"), "PowerPlatformConnectors": ("microsoft/PowerPlatformConnectors", "MIT"), "api-specs": ("wso2/api-specs", "Apache-2.0")}

# ---- exam #7 exclusions (final list from the coordinator; json file wins if present) ----
EXAM7 = {
    "ringcentral": dict(names=["ringcentral", "ring-central", "ringcentral-api", "ringcentral-api-docs"], domains=["ringcentral.com"], repos=["ringcentral/ringcentral-api-docs"]),
    "openziti": dict(names=["openziti", "ziti", "netfoundry"], domains=["openziti.io", "netfoundry.io"], repos=["openziti/edge-api"]),
    "gitness": dict(names=["gitness", "harness", "harness-code", "harnessio"], domains=["harness.io"], repos=["harness/gitness"]),
    "huggingface": dict(names=["huggingface", "hugging-face"], domains=["huggingface.co"], repos=[]),
    "pipedrive": dict(names=["pipedrive"], domains=["pipedrive.com"], repos=[]),
    "vikunja": dict(names=["vikunja", "go-vikunja"], domains=["vikunja.io"], repos=["go-vikunja/vikunja"]),
    "gitbook": dict(names=["gitbook"], domains=["gitbook.com"], repos=[]),
    "baserow": dict(names=["baserow"], domains=["baserow.io"], repos=[]),
    "looker": dict(names=["looker", "looker-open-source"], domains=["looker.com"], repos=["looker-open-source/sdk-codegen"]),
    "wekan": dict(names=["wekan"], domains=["wekan.github.io"], repos=["wekan/wekan"]),
    "shortcut": dict(names=["shortcut", "clubhouse"], domains=["shortcut.com", "clubhouse.io"], repos=[]),
    "bitrise": dict(names=["bitrise"], domains=["bitrise.io"], repos=[]),
}
EX_FILE = os.path.join(D, "exam7-exclusions.json")


def load_exam7():
    """built-in list, unioned with data/r15/exam7-exclusions.json (groups exam/reserve, {aliases, repos}) when present."""
    ex = {v: {k: list(x) for k, x in spec.items()} for v, spec in EXAM7.items()}
    if not os.path.exists(EX_FILE):
        return ex, "builtin"
    try:
        j = json.load(open(EX_FILE))
        for grp in ("exam", "reserve"):
            for v, spec in (j.get(grp) or {}).items():
                e = ex.setdefault(v, dict(names=[], domains=[], repos=[]))
                for a in spec.get("aliases", []):
                    (e["domains"] if "." in a else e["names"]).append(a)
                e["repos"] += spec.get("repos", [])
        return ex, "builtin+" + EX_FILE
    except Exception:
        return ex, "builtin (json unreadable)"


def toks(text):
    t = [x for x in re.split(r"[^a-z0-9]+", s(text).lower()) if x]
    c = set(t)
    c.update(a + b for a, b in zip(t, t[1:]))
    if t:
        c.add("".join(t))
    return c


def make_exam_matcher(ex):
    vend = {}
    for v, spec in ex.items():
        if not isinstance(spec, dict):
            continue
        vend[v] = ([ids.norm(n) for n in spec.get("names", spec.get("aliases", [])) if ids.norm(n)] + [ids.norm(v)],
                   [d.lower() for d in spec.get("domains", [])],
                   [r.lower() for r in spec.get("repos", [])])

    def match(host_list, name_fields, other_domains, path):
        """return (vendor, rule) or None.  host: server/host domains; alias: whole-label of a domain; name: folder/title/publisher."""
        for v, (names, doms, repos) in vend.items():
            for h in host_list:
                if any(h == d or h.endswith("." + d) for d in doms):
                    return v, "host"
            for h in host_list:
                if any(n in {ids.norm(l) for l in h.split(".")} for n in names):
                    return v, "host"
        for v, (names, doms, repos) in vend.items():
            for h in other_domains:
                if any(h == d or h.endswith("." + d) for d in doms):
                    return v, "contact"
                if any(n in {ids.norm(l) for l in h.split(".")} for n in names):
                    return v, "alias"
        for v, (names, doms, repos) in vend.items():
            for f in name_fields:
                tk = toks(f)
                if any(n in tk for n in names):
                    return v, "name"
            pl = path.lower()
            if any(r in pl for r in repos) or any(n in toks(path) for n in [x for x in names if len(x) >= 5]):
                return v, "repo"
        return None
    return match


# ---- parsing ----
def load_spec(path):
    raw = open(path, "rb").read().decode("utf-8-sig", "replace")
    return json.loads(raw) if path.lower().endswith(".json") else yaml.load(raw, Loader=Loader)


def pp_meta(folder, d):
    pub, web, priv = "", "", ""
    for e in (d.get("x-ms-connector-metadata") or []):
        if isinstance(e, dict):
            n = s(e.get("propertyName")).lower()
            if n == "website":
                web = s(e.get("propertyValue"))
            elif "privacy" in n:
                priv = s(e.get("propertyValue"))
            elif n == "publisher":
                pub = s(e.get("propertyValue"))
    try:
        ap = json.load(open(os.path.join(folder, "apiProperties.json"), encoding="utf-8-sig"))
        p = ap.get("properties", {}) if isinstance(ap, dict) else {}
        pub = pub or s(p.get("publisher"))
        web = web or s(p.get("website"))
        priv = priv or s(p.get("privacyPolicy") or p.get("privacy-policy"))
    except Exception:
        pass
    return pub, web, priv


def parse(d, src, repo, licence, rel, folder_name, pub, web, priv, repo_url):
    """-> (spec_summary, rows).  rows are dicts keyed by OUT_COLS + extras."""
    ver = s(d.get("openapi")) if "openapi" in d else s(d.get("swagger"))
    paths = d.get("paths")
    if not isinstance(paths, dict) or not (ver.startswith("3") or ver.startswith("2")):
        return None
    info = d.get("info") if isinstance(d.get("info"), dict) else {}
    title = s(info.get("title"))
    contact = info.get("contact") if isinstance(info.get("contact"), dict) else {}
    logo = info.get("x-logo") if isinstance(info.get("x-logo"), dict) else {}
    servers = extract.server_urls(d)
    sdoms = sorted({x for x in (ids.domain(u) for u in servers) if x and not ids.is_generic_domain(x)})
    cd = []
    for u in (contact.get("url"), contact.get("email"), info.get("termsOfService"), web, priv):
        x = ids.domain(s(u)) if u else None
        if x and not ids.is_generic_domain(x):
            cd.append(x)
    cdoms = sorted(set(cd))
    ldom = ids.domain(s(logo.get("url"))) if logo.get("url") else None
    ldom = ldom if ldom and not ids.is_generic_domain(ldom) else ""
    tn = ids.norm_title(title)
    fn = ids.norm(folder_name)
    if sdoms:
        vk, vs = sdoms[0], "server"
    elif cdoms:
        vk, vs = cdoms[0], "contact"
    elif tn and tn not in ids.GENERIC_TITLES and len(tn) >= 3:
        vk, vs = "title:" + tn, "title"
    else:
        vk, vs = "owner:" + fn, "owner"
    shaw = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()
    hosts = sorted({h for h in (ids.host_of(u) for u in servers) if h})
    rows = []
    for p, item in paths.items():
        if not isinstance(item, dict) or not isinstance(p, str) or not p.startswith("/"):
            continue
        for m in extract.METHODS:
            op = item.get(m) if m in item else item.get(m.upper())
            if not isinstance(op, dict):
                continue
            h = hashlib.sha256(("%s\0%s\0%s\0%s\0%s" % (repo, rel, shaw, m, p)).encode()).hexdigest()[:16]
            rows.append({
                "op_id": "r15c-" + h, "method": m.upper(), "path": p, "operationId": s(op.get("operationId")),
                "summary": s(op.get("summary")), "description": s(op.get("description")), "spec_title": title,
                "spec_version_field": ver, "servers": "|".join(servers), "x_logo": s(logo.get("url")),
                "contact_url": s(contact.get("url")), "contact_email": s(contact.get("email")),
                "contact_domain": "|".join(cdoms), "servers_domains": "|".join(sdoms), "logo_domain": ldom,
                "repo": repo, "repo_owner": repo.split("/")[0], "repo_name": repo.split("/")[1], "file_path": rel,
                "licence": licence, "is_fork": False, "fork_parent": "", "stars": None, "pushed_at": "",
                "spec_sha256": shaw, "vendor_key": vk, "vendor_key_source": vs, "title_norm": tn, "source": src,
                "visibility": s(op.get("x-ms-visibility")), "deprecated": bool(op.get("deprecated")),
                "repo_url": repo_url, "folder": folder_name, "publisher": pub, "website": web, "privacy_url": priv,
                "_hosts": "|".join(hosts), "_folder_norm": fn})
    return rows


# ---- activepieces: literal httpClient.sendRequest calls inside createAction files ----
Q = r"""(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`)"""
CONST_RE = re.compile(r"(?:const|let)\s+(\w+)\s*(?::\s*string)?\s*=\s*(?:'([^'\n]*)'|\"([^\"\n]*)\"|`([^`\n]*)`)")


def strlit(m, i=1):
    return next((g for g in m.groups()[i - 1:i + 2] if g is not None), "")


def balanced(txt, start):
    """text inside the paren group opening at txt[start]=='('"""
    depth, i = 0, start
    while i < len(txt):
        c = txt[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return txt[start + 1:i]
        i += 1
    return txt[start + 1:]


def resolve_url(expr, consts):
    expr = expr.strip().rstrip(",").strip()
    parts = [x.strip() for x in re.split(r"\s\+\s", expr)]
    out = ""
    for part in parts:
        m = re.fullmatch(r"'([^']*)'|\"([^\"]*)\"|`([^`]*)`", part)
        if m:
            lit = next(g for g in m.groups() if g is not None)
            out += re.sub(r"\$\{\s*(\w+)\s*\}", lambda k: consts.get(k.group(1), "${%s}" % k.group(1)), lit)
        elif re.fullmatch(r"\w+", part) and part in consts:
            out += consts[part]
        elif re.fullmatch(r"[\w.]+", part) and not out:
            out += "${%s}" % part  # unknown leading variable: base unknown
        else:
            return None
    return out


def url_to_hostpath(u):
    if u is None:
        return None
    u = re.sub(r"\$\{[^}]*\}", "\0", u) if False else u
    m = re.match(r"^(https?://)([^/?#]+)(.*)$", u)
    host, rest = "", u
    if m:
        host, rest = m.group(2), m.group(3)
        if "${" in host:
            host = ""
    else:
        rest = re.sub(r"^(\$\{\w[\w.]*\})+", "", u) if u.startswith("${") else u
    rest = rest.split("?")[0].split("#")[0]
    rest = re.sub(r"\$\{[^}]*\}", "{}", rest)
    if not rest.startswith("/") or "$" in rest or "`" in rest:
        return None
    return host, rest


def collect_activepieces(found, bad):
    base = os.path.join(CAT, "activepieces", "repo")
    comm = os.path.join(base, "packages", "pieces", "community")
    repo, lic = REPOS["activepieces"]
    rows = []
    pieces = sorted(g for g in glob.glob(os.path.join(comm, "*")) if os.path.isdir(g))
    st = {"specs_found": len(pieces), "specs_parsed": 0, "pieces_with_createAction": 0, "pieces_with_literal_http_ops": 0,
          "pieces_with_ge5_http_ops": 0, "actions_total": 0, "actions_with_literal_http": 0}
    for pdir in pieces:
        name = os.path.basename(pdir)
        files = sorted(glob.glob(os.path.join(pdir, "src", "**", "*.ts"), recursive=True))
        files = [f for f in files if "/test" not in f and not f.endswith((".test.ts", ".spec.ts"))]
        texts = {}
        for f in files:
            try:
                texts[f] = open(f, encoding="utf-8", errors="replace").read()
            except Exception:
                pass
        consts = {}
        for tx in texts.values():
            for m in CONST_RE.finditer(tx):
                v = next(x for x in m.groups()[1:] if x is not None)
                if v.startswith(("http", "/")):
                    consts.setdefault(m.group(1), v)
        title = name
        try:
            mi = re.search(r"createPiece\(\{[^}]*?displayName:\s*['\"`]([^'\"`]+)", texts[os.path.join(pdir, "src", "index.ts")], re.S)
            title = mi.group(1) if mi else name
        except Exception:
            pass
        ops, hosts, shaparts = [], set(), []
        n_act = 0
        for f, tx in texts.items():
            if "createAction(" not in tx:
                continue
            n_act += 1
            ci = tx.index("createAction(")
            head = tx[ci:ci + 6000]
            pi = head.find("props:")
            top = head[:pi] if pi > 0 else head
            dn = re.search(r"displayName:\s*(?:'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`)", top)
            ds = re.search(r"\bdescription:\s*(?:'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`)", top)
            an = re.search(r"\bname:\s*['\"`]([^'\"`]+)", top)
            disp = next((g for g in dn.groups() if g is not None), "") if dn else ""
            desc = next((g for g in ds.groups() if g is not None), "") if ds else ""
            got = False
            for m in re.finditer(r"sendRequest\s*(?:<[^>(]*>)?\s*\(", tx):
                body = balanced(tx, m.end() - 1)
                mm = re.search(r"\bmethod:\s*HttpMethod\.([A-Z]+)", body)
                um = re.search(r"\burl:\s*([^\n]*?)(?:,\s*$|,\s*\w+:|\s*$)", body, re.M)
                if not mm or not um:
                    continue
                hp = url_to_hostpath(resolve_url(um.group(1), consts))
                if not hp:
                    continue
                got = True
                if hp[0]:
                    hosts.add(hp[0])
                ops.append((mm.group(1), hp[1], disp, desc, an.group(1) if an else "", os.path.relpath(f, base)))
            if got:
                shaparts.append(tx)
        st["actions_total"] += n_act
        if n_act:
            st["pieces_with_createAction"] += 1
        if ops:
            st["pieces_with_literal_http_ops"] += 1
            if len(ops) >= 5:
                st["pieces_with_ge5_http_ops"] += 1
        st["actions_with_literal_http"] += len(shaparts)
        if not ops:
            bad.setdefault("activepieces", []).append(name + ": no literal sendRequest ops")
            continue
        st["specs_parsed"] += 1
        servers = sorted(hosts)
        sdoms = sorted({x for x in (ids.domain(u) for u in servers) if x and not ids.is_generic_domain(x)})
        tn = ids.norm_title(title)
        fn = ids.norm(name)
        if sdoms:
            vk, vs = sdoms[0], "server"
        elif tn and tn not in ids.GENERIC_TITLES and len(tn) >= 3:
            vk, vs = "title:" + tn, "title"
        else:
            vk, vs = "owner:" + fn, "owner"
        shaw = hashlib.sha256("\0".join(sorted(shaparts)).encode()).hexdigest()
        for meth, pth, disp, desc, opn, fpath in ops:
            h = hashlib.sha256(("%s\0%s\0%s\0%s\0%s" % (repo, fpath, shaw, meth, pth)).encode()).hexdigest()[:16]
            rows.append({
                "op_id": "r15c-" + h, "method": meth, "path": pth, "operationId": opn, "summary": disp, "description": desc,
                "spec_title": title, "spec_version_field": "", "servers": "|".join(servers), "x_logo": "", "contact_url": "",
                "contact_email": "", "contact_domain": "", "servers_domains": "|".join(sdoms), "logo_domain": "",
                "repo": repo, "repo_owner": repo.split("/")[0], "repo_name": repo.split("/")[1], "file_path": os.path.relpath(pdir, base),
                "licence": lic, "is_fork": False, "fork_parent": "", "stars": None, "pushed_at": "", "spec_sha256": shaw,
                "vendor_key": vk, "vendor_key_source": vs, "title_norm": tn, "source": "activepieces",
                "visibility": "", "deprecated": False, "repo_url": "https://github.com/" + repo, "folder": name,
                "publisher": "", "website": "", "privacy_url": "", "_hosts": "|".join(sorted(ids.host_of(u) or "" for u in servers)),
                "_folder_norm": fn})
    st["share_pieces_with_literal_http_ops"] = round(st["pieces_with_literal_http_ops"] / max(1, len(pieces)), 4)
    st["share_pieces_with_ge5_http_ops"] = round(st["pieces_with_ge5_http_ops"] / max(1, len(pieces)), 4)
    found["activepieces"] = st
    return rows



def collect():
    found, rows, bad = {}, [], {}
    base = os.path.join(CAT, "PowerPlatformConnectors")
    repo, lic = REPOS["PowerPlatformConnectors"]
    for src in SRC_ORDER[:3]:
        folders = sorted(g for g in glob.glob(os.path.join(base, PP[src], "*")) if os.path.isdir(g))
        found[src] = {"specs_found": len(folders), "specs_parsed": 0}
        for f in folders:
            cand = [x for x in os.listdir(f) if x.lower().endswith(".json") and ("swagger" in x.lower() or x.lower().startswith("apidef"))]
            if not cand:
                bad.setdefault(src, []).append(os.path.basename(f) + ": no swagger file")
                continue
            fp = os.path.join(f, sorted(cand)[0])
            try:
                d = load_spec(fp)
                pub, web, priv = pp_meta(f, d)
                r = parse(d, src, repo, lic, os.path.relpath(fp, base), os.path.basename(f), pub, web, priv,
                          "https://github.com/" + repo)
            except Exception as e:
                bad.setdefault(src, []).append("%s: %s" % (os.path.basename(f), type(e).__name__))
                continue
            if r is None:
                bad.setdefault(src, []).append(os.path.basename(f) + ": not a spec")
                continue
            found[src]["specs_parsed"] += 1
            rows += r
    base = os.path.join(CAT, "api-specs")
    repo, lic = REPOS["api-specs"]
    apis = sorted(g for g in glob.glob(os.path.join(base, "openapi", "*", "*")) if os.path.isdir(g))
    found["wso2"] = {"specs_found": 0, "specs_parsed": 0, "vendor_folders": len({a.split("/")[-2] for a in apis}), "api_folders": len(apis)}

    def vkey(v):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", v)]
    for a in apis:
        vers = [v for v in os.listdir(a) if os.path.isdir(os.path.join(a, v))]
        if not vers:
            continue
        v = sorted(vers, key=vkey)[-1]
        fs = [x for x in ("openapi.yaml", "openapi.yml", "openapi.json") if os.path.exists(os.path.join(a, v, x))]
        if not fs:
            continue
        found["wso2"]["specs_found"] += 1
        fp = os.path.join(a, v, fs[0])
        try:
            d = load_spec(fp)
            vendor = a.split("/")[-2]
            r = parse(d, "wso2", repo, lic, os.path.relpath(fp, base), vendor + "/" + a.split("/")[-1], "", "", "",
                      "https://github.com/" + repo)
        except Exception as e:
            bad.setdefault("wso2", []).append("%s: %s" % (a, type(e).__name__))
            continue
        if r is None:
            bad.setdefault("wso2", []).append(a + ": not a spec")
            continue
        found["wso2"]["specs_parsed"] += 1
        rows += r
    # konfig: <vendor>/openapi.yaml or <vendor>/<api>/openapi.yaml; about.json gives company / homepage
    base = os.path.join(CAT, "openapi-examples")
    repo, lic = REPOS["openapi-examples"]
    kf = sorted(g for g in glob.glob(os.path.join(base, "*", "openapi.yaml")) + glob.glob(os.path.join(base, "*", "*", "openapi.yaml")))
    found["konfig"] = {"specs_found": len(kf), "specs_parsed": 0, "vendor_folders": len({os.path.relpath(f, base).split("/")[0] for f in kf})}
    for fp in kf:
        vendor = os.path.relpath(fp, base).split("/")[0]
        try:
            d = load_spec(fp)
            about = {}
            try:
                about = json.load(open(os.path.join(base, vendor, "about.json"), encoding="utf-8-sig"))
            except Exception:
                pass
            r = parse(d, "konfig", repo, lic, os.path.relpath(fp, base), vendor, s(about.get("company")), s(about.get("homepage")),
                      s(about.get("developerDocumentation")), "https://github.com/" + repo)
        except Exception as e:
            bad.setdefault("konfig", []).append("%s: %s" % (fp, type(e).__name__))
            continue
        if r is None:
            bad.setdefault("konfig", []).append(fp + ": not a spec")
            continue
        found["konfig"]["specs_parsed"] += 1
        rows += r
    rows += collect_activepieces(found, bad)
    return pd.DataFrame(rows), found, bad


def per_src(df):
    return {k: int(v) for k, v in df["source"].value_counts().to_dict().items()}


def per_src_vendors(df):
    return {k: int(v) for k, v in df.groupby("source")["vendor_key"].nunique().to_dict().items()}


def main():
    rep = {"licence_notes": {"konfig": "konfig-sdks/openapi-examples has no LICENSE file and GitHub's licence field is null "
                                       "(README badge says MIT); included per the 2026-11-18 user decision (permissive-only rule "
                                       "dropped for public API definitions); licence column says unknown"}}
    df, found, bad = collect()
    rep["specs"] = found
    rep["unparseable"] = {k: v[:20] for k, v in bad.items()}
    rep["unparseable_counts"] = {k: len(v) for k, v in bad.items()}
    df["_spec"] = df["source"] + "\0" + df["file_path"] + "\0" + df["spec_sha256"]
    rep["ops_raw"] = per_src(df)
    rep["specs_raw"] = {k: int(v) for k, v in df.groupby("source")["_spec"].nunique().to_dict().items()}

    # 1. template
    tnorm = df["spec_title"].str.lower().str.strip()
    title_bad = tnorm.str.match(flt.TEMPLATE_TITLE_RE) | tnorm.str.contains("petstore", regex=False)
    df["_pn"] = df["path"].map(ids.op_path_norm)
    g = df.assign(_t=df["_pn"].isin(flt.TEMPLATE_PATHS)).groupby("_spec")["_t"].agg(["sum", "count"])
    pb = set(g.index[(g["sum"] >= flt.TEMPLATE_PATH_MIN_HITS) & (g["sum"] / g["count"] >= flt.TEMPLATE_PATH_MIN_FRAC)])
    bad_m = title_bad | df["_spec"].isin(pb)
    rep["template_dropped_specs"] = sorted(df.loc[bad_m, "_spec"].map(lambda x: x.split("\0")[1]).unique())[:50]
    df = df[~bad_m]
    rep["ops_after_template_drop"] = per_src(df)
    # 2. min 5
    df = df[df.groupby("_spec")["op_id"].transform("count") >= flt.MIN_OPS]
    rep["ops_after_min5"] = per_src(df)
    # 3. spec dedupe (source order, then path)
    df = df.assign(_so=df["source"].map({k: i for i, k in enumerate(SRC_ORDER)}))
    df = df.sort_values(["_so", "file_path"], kind="mergesort")
    first = df.drop_duplicates("spec_sha256").set_index("spec_sha256")["_spec"]
    df = df[df["_spec"] == df["spec_sha256"].map(first)]
    rep["ops_after_spec_dedupe"] = per_src(df)
    # 4. op dedupe
    df = df.drop_duplicates(["vendor_key", "method", "_pn"])
    rep["ops_after_op_dedupe"] = per_src(df)
    rep["vendors_after_op_dedupe"] = per_src_vendors(df)
    rep["vendors_after_op_dedupe_total"] = int(df["vendor_key"].nunique())

    # 5a. exam #7
    ex, exsrc = load_exam7()
    rep["exam7_source"] = exsrc
    match = make_exam_matcher(ex)
    idc = df[["vendor_key", "file_path", "folder", "spec_title", "publisher", "_hosts", "contact_domain", "logo_domain", "website", "privacy_url"]].drop_duplicates()
    verdict = {}
    for r in idc.itertuples(index=False):
        other = [d for d in (r.contact_domain + "|" + r.logo_domain).split("|") if d]
        for u in (r.website, r.privacy_url):
            h = ids.host_of(u) if u else None
            if h:
                other.append(h)
        verdict[tuple(r)] = match([h for h in r[5].split("|") if h],
                                  [r.folder, r.spec_title, r.publisher], other, r.file_path)
    keyed = [tuple(x) for x in df[idc.columns].itertuples(index=False)]
    vv = [verdict[k] for k in keyed]
    hit = pd.Series([v is not None for v in vv], index=df.index)
    drops = {}
    for (v, rule), src, o in zip([x or (None, None) for x in vv], df["source"], [1] * len(df)):
        if v:
            e = drops.setdefault(v, {}).setdefault(src, {}).setdefault(rule, 0)
            drops[v][src][rule] = e + 1
    dd = df[hit]
    ex_examples = {}
    for (v, src), gdf in dd.assign(_v=[x[0] for x in vv if x]).groupby(["_v", "source"]):
        ex_examples.setdefault(v, {})[src] = sorted(gdf["folder"].unique())[:10]
    rep["exam7_dropped_ops_by_vendor_source_rule"] = drops
    rep["exam7_dropped_examples"] = ex_examples
    df = df[~hit]
    rep["ops_after_exam7"] = per_src(df)

    # 5b. corpus exclusion (same key mechanism as filter.py; repo owner/name deliberately NOT used:
    #     they are the catalogue repos, not vendors)
    keys, srcs = flt.build_exclusions(None)
    rep["exclusion"] = dict(srcs, keys=len(keys))

    def ident(r):
        k = set()
        if r.vendor_key.startswith(("title:", "owner:")):
            n = r.vendor_key.split(":", 1)[1]
            if len(n) >= 4 and n not in flt.GENERIC_NAMES:
                k.add("n:" + n)
        else:
            k |= flt.name_keys(r.vendor_key)
        for dm in (r.servers_domains + "|" + r.contact_domain + "|" + r.logo_domain).split("|"):
            if dm:
                k |= flt.name_keys(dm)
        for n in (r.title_norm, r[5]):
            if len(n) >= 4 and n not in flt.GENERIC_NAMES:
                k.add("n:" + n)
        return k
    idc = df[["vendor_key", "servers_domains", "contact_domain", "logo_domain", "title_norm", "_folder_norm"]].drop_duplicates()
    hm = {}
    for r in idc.itertuples(index=False):
        hm[tuple(r)] = sorted(ident(r) & keys)
    m = [hm[tuple(r)] for r in df[idc.columns].itertuples(index=False)]
    seen = pd.Series([bool(x) for x in m], index=df.index)
    sd = df[seen].assign(_k=[x[0] for x in m if x])
    rep["already_seen_dropped"] = {
        "vendors_by_source": per_src_vendors(sd), "ops_by_source": per_src(sd),
        "vendors_total": int(sd["vendor_key"].nunique()),
        "examples": {src: [{"vendor_key": a, "matched_key": b} for a, b in
                           sd[sd.source == src].drop_duplicates("vendor_key")[["vendor_key", "_k"]].head(15).itertuples(index=False)]
                     for src in SRC_ORDER}}
    df = df[~seen]
    rep["ops_after_exclusion"] = per_src(df)
    rep["vendors_after_exclusion"] = per_src_vendors(df)

    # 6. cap
    df = df.assign(_h=[hashlib.sha256((flt.SEED + o).encode()).hexdigest() for o in df["op_id"]])
    df = df.sort_values(["vendor_key", "_h"]).groupby("vendor_key", sort=False).head(flt.CAP)
    rep["ops_after_cap"] = per_src(df)
    rep["vendors_final"] = per_src_vendors(df)
    rep["ops_final_total"] = len(df)
    rep["vendors_final_total"] = int(df["vendor_key"].nunique())
    vc = df["vendor_key"].value_counts()
    rep["top10_vendors"] = {k: int(v) for k, v in vc.head(10).items()}
    rep["ops_per_vendor"] = {"min": int(vc.min()), "median": float(vc.median()), "max": int(vc.max()), "vendors_at_cap": int((vc >= flt.CAP).sum())}
    try:
        prev = set(pd.read_parquet(os.path.join(D, "ops-r15.parquet"), columns=["vendor_key"])["vendor_key"])
        rep["vendor_keys_also_in_ops_r15_not_dropped"] = sorted(set(df["vendor_key"]) & prev)[:100]
    except Exception:
        pass

    out = df.sort_values(["vendor_key", "op_id"]).reset_index(drop=True)
    extra = ["visibility", "deprecated", "repo_url", "folder", "publisher", "website", "privacy_url"]
    out["stars"] = out["stars"].astype("Int64")
    out[OUT_COLS + extra].to_parquet(os.path.join(D, "ops-r15-catalogues.parquet"), index=False)
    out[OUT_COLS].to_csv(os.path.join(D, "ops-r15-catalogues.csv.gz"), index=False, compression="gzip")
    out[["op_id"] + extra].to_csv(os.path.join(D, "ops-r15-catalogues-extra.csv.gz"), index=False, compression="gzip")

    def j(x):
        return "|".join(sorted({v for v in x if v}))[:5000]
    prov = []
    for vk, g_ in out.groupby("vendor_key"):
        prov.append({"vendor": vk, "keys_aliases": j([vk] + [d for x in g_["servers_domains"].unique() for d in x.split("|")] +
                                                      [d for x in g_["contact_domain"].unique() for d in x.split("|")] +
                                                      list(g_["title_norm"].unique()) + list(g_["folder"].unique())),
                     "source": j(g_["source"].unique()),
                     "repo_url": j(g_["repo_url"].unique()), "ops": len(g_)})
    pd.DataFrame(prov).sort_values("ops", ascending=False).to_csv(os.path.join(D, "providers-r15-catalogues.csv"), index=False)
    json.dump(rep, open(os.path.join(D, "collect-report-catalogues.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in rep.items() if k in ("ops_raw", "ops_after_cap", "vendors_final", "ops_final_total", "vendors_final_total", "top10_vendors")}, indent=1))


if __name__ == "__main__":
    main()
