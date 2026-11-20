#!/usr/bin/env python3
"""r15 cloud-vendor API catalogues: Alibaba Cloud (aliyun/aliyun-openapi-meta, Apache-2.0) and Huawei Cloud
(huaweicloud/huaweicloud-sdk-python-v3, Apache-2.0).  QUARANTINED: parse + table building only, no labelling.
Clones live under data/r15/raw/cloud/ (shallow).  Every product/service is its own vendor_key
(aliyun:<product>, huaweicloud:<service>) so the 300-ops cap applies per product.
Outputs: data/r15/ops-r15-cloud.{csv.gz,parquet}, providers-r15-cloud.csv, collect-report-cloud.json.
Activepieces is NOT done here (the catalogues worker owns it).
Run:  nice -n 19 ionice -c3 python3 r15/cloud.py
"""
import glob, hashlib, json, os, re, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ids, extract, filter as flt, swaggerhub as sh

D = flt.D
CLOUD = os.path.join(D, "raw", "cloud")
ALI = os.path.join(CLOUD, "aliyun-openapi-meta")
HW = os.path.join(CLOUD, "huaweicloud-sdk-python-v3")
OUT_COLS = extract.COLS + ["source", "api_style", "product"]
ids.GENERIC_HOSTS.update({"azure-api.net", "azure-apim.net", "azure.net"})
s = extract.s


def vkey(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", v)]


def base_row(src, vendor_key, product, title, repo, repo_name, fpath, lic, servers, sha, desc_pair, method, path, opid, style):
    sdoms = sorted({x for x in (ids.domain(u) for u in servers) if x and not ids.is_generic_domain(x)})
    h = hashlib.sha256(("%s\0%s\0%s\0%s\0%s" % (src, fpath, opid, method, path)).encode()).hexdigest()[:16]
    return {"op_id": "r15x-" + h, "method": method, "path": path, "operationId": opid, "summary": desc_pair[0],
            "description": desc_pair[1], "spec_title": title, "spec_version_field": "", "servers": "|".join(servers),
            "x_logo": "", "contact_url": "", "contact_email": "", "contact_domain": "", "servers_domains": "|".join(sdoms),
            "logo_domain": "", "repo": repo, "repo_owner": repo.split("/")[0], "repo_name": repo_name, "file_path": fpath,
            "licence": lic, "is_fork": False, "fork_parent": "", "stars": None, "pushed_at": "", "spec_sha256": sha,
            "vendor_key": vendor_key, "vendor_key_source": "product", "title_norm": ids.norm_title(title),
            "source": src, "api_style": style, "product": product}


def collect_alibaba(st):
    prods = {p["code"].lower(): p for p in json.load(open(os.path.join(ALI, "metadatas", "products.json")))["products"]}
    rows = []
    st["products_in_metadata"] = len(prods)
    st["product_dirs"] = 0; st["apis_total"] = 0; st["apis_skipped_no_method_or_path"] = 0; st["apis_rpc"] = 0; st["apis_roa"] = 0
    for pd_ in sorted(glob.glob(os.path.join(ALI, "canonical", "*"))):
        code = os.path.basename(pd_); st["product_dirs"] += 1
        p = prods.get(code.lower(), {})
        title = (p.get("name") or {}).get("en") or code
        ep = p.get("global_endpoint") or next(iter((p.get("regional_endpoints") or {}).values()), "")
        servers = ["https://" + ep] if ep else []
        for vd in sorted(glob.glob(os.path.join(pd_, "*")), key=lambda x: vkey(os.path.basename(x))):
            ver = os.path.basename(vd)
            files = sorted(f for f in glob.glob(os.path.join(vd, "*.json")) if not f.endswith("version.json"))
            if not files:
                continue
            blobs = [open(f, "rb").read() for f in files]
            sha = hashlib.sha256(b"".join(hashlib.sha256(b).hexdigest().encode() for b in blobs)).hexdigest()
            fpath = "canonical/%s/%s" % (code, ver)
            for b in blobs:
                d = json.loads(b); o = d.get("operation") or {}; st["apis_total"] += 1
                method = s(o.get("method")).upper().split("|")[0].strip()
                action = s(o.get("action") or d.get("name"))
                style = "rpc" if s(o.get("api_style")).upper() == "RPC" else "roa"
                url = s(o.get("url") or d.get("pathPattern"))
                if style == "roa":
                    path = url
                    if not method or not path.startswith("/"):
                        st["apis_skipped_no_method_or_path"] += 1; continue
                else:
                    path = action
                    if not method or not path:
                        st["apis_skipped_no_method_or_path"] += 1; continue
                st["apis_" + style] += 1
                desc = s(d.get("description_en")).strip()
                rows.append(base_row("alibaba", "aliyun:" + code.lower(), code, title, "aliyun/aliyun-openapi-meta", code,
                                     fpath, "Apache-2.0", servers, sha, ("", desc), method, path, action, style))
    return rows


RE_FUNC = re.compile(r'    def (_\w+)_http_info\(cls, request\):\s*\n\s*http_info = \{\s*\n\s*"method": "(\w+)",\s*\n\s*"resource_path": "([^"]*)"')
RE_DOC = re.compile(r'    def (\w+)\(self, request\):\s*\n\s*r"""(.*?)"""', re.S)


def collect_huawei(st):
    rows = []
    sd = sorted(glob.glob(os.path.join(HW, "huaweicloud-sdk-*")))
    st["sdk_dirs"] = len(sd); st["services_with_client"] = 0; st["apis_total"] = 0; st["apis_unparsed"] = 0
    for dd in sd:
        svc = os.path.basename(dd).split("huaweicloud-sdk-", 1)[1]
        if svc in ("core", "all"):
            continue
        clients = sorted(f for f in glob.glob(os.path.join(dd, "huaweicloudsdk*", "v*", "*_client.py")) if "async" not in f)
        if not clients:
            continue
        st["services_with_client"] += 1
        for cf in clients:
            ver = cf.split("/")[-2]
            txt = open(cf, encoding="utf-8").read()
            docs = {m.group(1): m.group(2) for m in RE_DOC.finditer(txt)}
            servers = []
            rg = glob.glob(os.path.join(os.path.dirname(cf), "region", "*_region.py"))
            if rg:
                m = re.search(r'"(https://[^"]+)"', open(rg[0], encoding="utf-8").read())
                if m:
                    servers = [m.group(1)]
            title = svc.upper()
            defs = txt.count("_http_info(cls, request)")
            found = 0
            fpath = "%s/%s/%s" % (os.path.basename(dd), ver, os.path.basename(cf))
            sha = hashlib.sha256(txt.encode()).hexdigest()
            for m in RE_FUNC.finditer(txt):
                name = m.group(1).lstrip("_"); method = m.group(2).upper(); path = m.group(3)
                if not path.startswith("/"):
                    continue
                dl = [x.strip() for x in docs.get(name, "").split("\n")]
                first = next((x for x in dl if x), "")
                found += 1
                rows.append(base_row("huawei", "huaweicloud:" + svc, svc, title, "huaweicloud/huaweicloud-sdk-python-v3", "huaweicloud-sdk-" + svc,
                                     fpath, "Apache-2.0", servers, sha, ("", first), method, path, name, "roa"))
            st["apis_total"] += defs; st["apis_unparsed"] += defs - found
    return rows


def main():
    rep = {"user_decision": "2026-11-18: permissive-licence rule dropped for public API definitions; licence column kept",
           "licence_notes": "aliyun-openapi-meta LICENSE: Apache-2.0; huaweicloud-sdk-python-v3 LICENSE header: Apache-2.0",
           "activepieces": "not done here: catalogues worker owns it (data/r15/raw/catalogues/activepieces exists)"}
    sa, sh_ = {}, {}
    rows = collect_alibaba(sa) + collect_huawei(sh_)
    rep["alibaba_parse"] = sa; rep["huawei_parse"] = sh_
    df = pd.DataFrame(rows)
    df = sh.finish(df, rep, "cloud")
    sh.write_outputs(df, rep, "cloud", OUT_COLS)
    print(json.dumps({k: v for k, v in rep.items() if not isinstance(v, (dict, list, str))}, indent=1))
    for k in ("ops_raw", "ops_after_template_drop", "ops_after_min5", "ops_after_spec_dedupe", "ops_after_op_dedupe", "ops_after_exam7", "ops_after_corpus_exclusion", "ops_after_cap", "vendors_final"):
        print(k, rep[k])


if __name__ == "__main__":
    main()
