"""Lean rule names the model text writes differently from rwxmap. ONE place for round 10's final assembly and
for the check; mirrors LEAN_RULE_ALIASES in src/text.js (test/aliases.test.js and `python3 m1/round10_aliases.py` assert equality)."""
import json, os, re, subprocess

LEAN_RULE_ALIASES = {'credential-set': 'cant-undo-verb'}

def text_rule(rule): return LEAN_RULE_ALIASES.get(rule, rule)

def js_table():
    """Parse the table out of src/text.js (no import, so no build step)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'text.js')).read()
    body = re.search(r'const LEAN_RULE_ALIASES\s*=\s*\{([^}]*)\}', src).group(1)
    return dict(re.findall(r"'([^']+)'\s*:\s*'([^']+)'", body))

def check():
    js = js_table()
    assert js == LEAN_RULE_ALIASES, f'alias drift: src/text.js {js} != m1/round10_aliases.py {LEAN_RULE_ALIASES}'
    return js

if __name__ == '__main__': print('ok', check())
