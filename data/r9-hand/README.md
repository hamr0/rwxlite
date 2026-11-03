# Round 9 hand-label sample

Purpose: rows to hand-label under BRIEF-v3 for added training weight. Targets the two shapes behind r8soft's too-loose exam rows: lower-tier POST rows the recipe lowered (mechanical x -> w/r) and raise-wx PUT/PATCH rows left at w.
Labellers see only blind.csv. key.csv (shape, vendor, current r6 label) must never be shown to them.

Selection (`train/r9_select.py`, seed 20261109), by shape only, no word/regex filter:
- 800 lower-tier POST rows, mechanical letter x, round-6 label w or r.
- 400 raise-wx PUT/PATCH rows, round-6 label w.
- Pool: train.parquet + val.parquet. r8soft probabilities exist only for val and v3eval rows, not train rows, so selection is seeded random (key.csv r8soft_p is empty).
- Vendor cap 40 per vendor (first dotted token of provider), across the whole sample; one row per op key (METHOD|path|operationId).
- Final seeded shuffle, ids r9-0001..r9-1200.

Exclusions (asserted in code): exam vendors/locked vendors and exam_opkey_overlap (already outside training), every id and every op key in gate-2026-11-03/-04/-06/-07 ids.txt, every v3 tuning truth row (id and op key, from v3eval.parquet).
Counts removed from pool of 91837: {'gate_id_or_opkey': 1669, 'v3_tuning_id_or_opkey': 74, 'pool': 91837, 'eligible': 90094, 'cand_lower': 15243, 'cand_raise': 9829}

Counts (shape, method, current label): {('lower-post', 'POST', 'w'): 602, ('raise-wx-putpatch', 'PATCH', 'w'): 108, ('raise-wx-putpatch', 'PUT', 'w'): 292, ('lower-post', 'POST', 'r'): 198}
Top vendors: [('googleapis', 40), ('azure', 40), ('amazonaws', 40), ('microsoft', 40), ('autotask', 40), ('netbox', 38), ('kubernetes', 30), ('vtex', 25), ('github', 24), ('twilio', 23)]
