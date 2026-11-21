#!/usr/bin/env python3
"""r16 audit of data/r16/ops-r16-github.csv.gz: re-checks exam #8 freeze, new-vendor rule and English-only on the OUTPUT file."""
import importlib.util, os, sys, json
import pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "..")
sp = importlib.util.spec_from_file_location("pd8", os.path.join(H, "pick_dev.py")); P = importlib.util.module_from_spec(sp); sp.loader.exec_module(P)
o = pd.read_csv(os.path.join(R, "data/r16/ops-r16-github.csv.gz"), dtype=str, keep_default_na=False)
m = pd.read_parquet(os.path.join(R, "data/r15/master/ops-r15-master.parquet"), columns=["vendor_id", "vendor_key", "spec_sha256", "servers_domains", "contact_domain", "logo_domain"])
res = {"rows": len(o), "lang_not_en": int((o["lang"] != "en").sum()), "no_text": int((o["has_text"] != "True").sum()),
       "vendor_in_master": int(o["vendor_key"].isin(set(m["vendor_id"]) | set(m["vendor_key"])).sum()),
       "spec_in_master": int(o["spec_sha256"].isin(set(m["spec_sha256"])).sum()),
       "max_ops_per_vendor": int(o["vendor_key"].value_counts().max()),
       "op_id_dupes": int(o["op_id"].duplicated().sum())}
md = set()
for c in ("servers_domains", "contact_domain", "logo_domain"):
    for v in m[c].dropna().unique():
        md.update(x for x in v.split("|") if x)
od = set()
res["vendor_domain_in_master_domains"] = int(sum(1 for v, k in zip(o["vendor_key"], o["vendor_kind"]) if k == "domain" and v in md))
res["servers_domain_in_master_domains"] = int(sum(1 for s in o["servers_domains"] if set(x for x in s.split("|") if x) & md))
d = o.drop_duplicates(["repo", "file_path", "spec_sha256"])
hit = [(r["repo"], r["file_path"]) for r in d.to_dict("records") if any(P.hits8(r))]
res["exam8_hits_whole_or_substring"] = len(hit); res["exam8_hit_examples"] = hit[:5]
print(json.dumps(res, indent=1))
