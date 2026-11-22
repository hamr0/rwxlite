# Round 16 teacher training set v3

Rows 360,536. Made by `r16/build_teacher_train.py --v3`. v2 rebuilt in memory (asserted equal to `teacher-train-v2.parquet` sha256 `9e1f3700...`), then: (1) `data/r16/review/rwxmap-unsure/answers-train.csv` (sha256 `92daa73b...`, 3,791 rows) applied to the 3,791 Sonnet-unsure rows (all found; all were label_source sonnet, unsure, weight 0.3): label = rwxmap_letter, label_source rwxmap, weight 1.0, prior_label kept; 894 of them changed letter vs Sonnet; (2) contested rows with label_source sonnet and sonnet_confidence sure: weight 3.0, weight_reason sonnet_sure_x3 (27,473 rows). Every other v2 weight kept (r15 replay 3.0, d143 3.0, exam7 3.0, likely 1.0). No row is Sonnet-unsure any more (asserted: 0 left).

## By part

new 299,600, holdout 400, replay-r13 20,378, replay-r15 39,617, extra-ruled 394, exam7 147

## By letter

r 176,914, x 101,327, w 82,295
(v2: r 176,887, x 100,801, w 82,848; letter changes v2 to v3: 894)

## By label_source

agree3 255,204, sonnet 40,079, replay_r15 39,210, replay_r13 20,309, rwxmap 5,587, exam7 147

## By weight

1.0 309,087, 3.0 51,449; total 463,434.0 (v2 total 405,834.3)

## By weight_reason

(none, 1.0 or 3.0 plain) 309,087, sonnet_sure_x3 27,473, r15_weight 23,390, d143_new 313, exam7 147, d143_r15 122, d143_r13 4

## Letter by part

| part | r | w | x |
|---|---|---|---|
| exam7 | 15 | 71 | 61 |
| extra-ruled | 61 | 119 | 214 |
| holdout | 116 | 135 | 149 |
| new | 152596 | 63463 | 83541 |
| replay-r13 | 11006 | 3265 | 6107 |
| replay-r15 | 13120 | 15242 | 11255 |

## The 3,791 unsure rows, Sonnet letter (rows) to rwxmap letter (columns)

| sonnet | r | w | x |
|---|---|---|---|
| r | 35 | 25 | 24 |
| w | 61 | 866 | 643 |
| x | 15 | 126 | 1996 |

## Dev v3

`final-labels-r16-dev-v3.{parquet,csv.gz}` from dev-v2 (sha256 `ef595578...`) plus `answers-dev-v3.csv` (sha256 `c123b896...`, 62 rows, all found, all label_source sonnet with the v2 label; label_source becomes rwxmap): 23 letters changed vs dev-v2 (12 w to x, 11 x to w). Extra columns: prior_label (v1, before D143, unchanged), prior_label_v2, d143_touched (the 9 D143 rows), unsure62. Dev letters v3: r 2,228, x 1,229, w 1,018 (v2: r 2,228, x 1,228, w 1,019). answers-dev.csv (v1) and answers-dev-v2.csv are superseded and not used.

Checks passed: unique ids; no train/dev overlap by id or exact opkey; no exam #8 vendor; letters r/w/x; weights > 0 (all 1.0 or 3.0); all 3,791 unsure rows found; no Sonnet-unsure row left; text, ids, parts unchanged from v2.
