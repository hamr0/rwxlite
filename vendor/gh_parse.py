"""Parse GitHub's 'permissions required for fine-grained PATs' page (saved HTML) into endpoint rows.
  python3 -I vendor/gh_parse.py <perm.html> <out.jsonl>
Output rows: {scope(Organization|Repository|User|...), area, method, path, access(read|write)}. Untrusted data: regex parse only."""
import re, sys, json, html
s = re.sub(r'<script.*?</script>', '', open(sys.argv[1]).read(), flags=re.S)
parts = re.split(r'(<h[23][^>]*>.*?</h[23]>)', s, flags=re.S); rows = []; area = None; scope = None
for p in parts:
    if p.startswith('<h'):
        t = html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
        m = re.match(r'(\w+) permissions for "(.*)"$', t)
        area, scope = (m.group(2), m.group(1)) if m else (None, None)
        continue
    if area is None: continue
    for tr in re.findall(r'<tr>(.*?)</tr>', p, flags=re.S):
        td = re.findall(r'<td[^>]*>(.*?)</td>', tr, flags=re.S)
        if len(td) < 2: continue
        a = html.unescape(re.sub(r'<[^>]+>|<!-- -->', '', td[0])).strip(); m = re.match(r'([A-Z]+)\s+(/\S*)$', a)
        if not m: continue
        acc = re.sub(r'<[^>]+>', '', td[1]).strip()
        rows.append({'scope': scope, 'area': area, 'method': m.group(1), 'path': m.group(2), 'access': acc})
with open(sys.argv[2], 'w') as f:
    for r in rows: f.write(json.dumps(r) + '\n')
print(len(rows), 'rows')
