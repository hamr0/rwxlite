"""Write test/fixtures/unescape.jsonl: Python's html.unescape (and the full clean pipeline) on many probes.
Run: python3 -I m1/make-unescape-fixture.py"""
import json
import random
import re
import sys
from html import unescape
from html.entities import html5

sys.path.insert(0, 'train')
rng = random.Random(1337)

def clean(s, n):  # train/common.py clean, restated so this script needs no imports from train/
    s = '' if s is None else str(s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = unescape(s)
    return re.sub(r'\s+', ' ', s).strip()[:n]

probes = ["Caf&eacute; &copy 2020 &frac12; &check; &lsqb;x&rsqb;", "&amp b", "&lt;x&gt", "&ensp;&emsp;", "&nbsp",
          "&#1;", "&#x7f;", "&#xfffe;", "&#0;", "&#128;", "&#x110000;", "&#xd800;", "&#65;bc", "&ampx", "&notit;",
          "&notin;", "&#", "&#x;", "&;", "&&amp;", "", "plain", "a & b", "&amp;amp;", "&#X41;", "&#65", "&#99999999999999999999;",
          "&unknown;", "&unknown", "&AMP", "&Amp;", "&notit", "&ltx", "&copyx", "&é;", "&😀;", "&#x1F600;", "&#8364;", "&#xD;"]
legacy = sorted(k for k in html5 if not k.endswith(';'))
for k in legacy:
    probes += ['&' + k, '&' + k + 'x', '&' + k + ';', 'a&' + k + ' b']
semi = sorted(k for k in html5 if k.endswith(';'))
probes += ['&' + k for k in rng.sample(semi, 150)]
probes += ['&' + k[:-1] for k in rng.sample(semi, 40)]
for _ in range(80):
    n = rng.choice([rng.randint(0, 0x9f), rng.randint(0xa0, 0xffff), rng.randint(0x10000, 0x10ffff), rng.randint(0x110000, 0x7fffffff),
                    rng.randint(0xd7f0, 0xe010), rng.randint(0xfdc0, 0xfdf0)])
    probes.append(rng.choice(['&#%d;', '&#%d', '&#x%x;', '&#X%X', 'z&#x%x;z']) % n)
for lo in (0xfffe, 0xffff, 0x1fffe, 0x10ffff, 0x10fffe, 0xfdd0, 0xfdef):
    probes += ['&#x%x;' % lo, '&#%d' % lo]

rows = [{'kind': 'unescape', 'in': p, 'out': unescape(p)} for p in probes]
pipeline = ['<p>Caf&eacute;&nbsp;&copy 2020</p>\n  <b>bold</b>&amp;co', '  a\t&lt;b&gt;   c\x1c d&#1;e ', '<a href="x">&#65;&notin;&notit;</a>',
            'Line1<br/>Line2 &frac12; &check; &lsqb;x&rsqb;', '&#xfffe;&#0;&#128;ok', '<![CDATA[x]]> &amp b']
for p in pipeline:
    for n in (5, 400):
        rows.append({'kind': 'clean', 'in': p, 'n': n, 'out': clean(p, n)})
with open('test/fixtures/unescape.jsonl', 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=True) + '\n')
print(len(rows), sys.version.split()[0])
