# r16 train-leakage check against exam #8

Requested by rwxmap (owner of exam #8) for its prereg. Collision counts only: no exam #8 labels or lean counts were read, computed or are reported here. Date 2026-11-23, branch r16-vendor-data. Script: `data/r16/scratch/leak/leak.py` (gitignored scratch; method below is complete).

## Inputs

| input | path | rows | sha256 |
|---|---|---|---|
| exam #8 ops (read only; columns used: id, provider, method, path, operationId, summary; sha verified) | rwxmap `data/exam8-2026-11-23/ops.csv` (rwxmap prereg c66a934) | 1,821 | 7d2be1f3167086597522025841c4a21e8eeb28095b2613f51e79237b21b428de |
| teacher-train-v3 (full teacher and student) | data/r16/train/teacher-train-v3.parquet | 360,536 | e5487eca839c164a919092df66094e25db77420c30edd51a015563f1d02a96b2 |
| small-run set A | data/r16/small/set-A.parquet | 35,999 | 26f102b83d01662da242efcb671e80eda52715ee96465f27336f37840869850e |
| small-run set B | data/r16/small/set-B.parquet | 60,177 | c89a66b5747a5dc3f0ff0e41ec43572ed7fbce4e1e139d19e8d3f1a531ae7d7c |
| round 15 train (inherited: r16 models continue from the r15 bases) | data/round15/train.parquet | 302,211 | 16a34b054aef3b6ca5ad084a2395f70596a086b3bf861eb29411066605213a99 |
| r16 dev v3 | data/r16/labels/final/final-labels-r16-dev-v3.parquet | 4,475 | b268b074c2225993e8f4dc146ea2d2672a8226f1932e20d27c1d9dfb507bceb5 |

## Method

1. Vendor/provider names. For each file the columns provider, vendor, vendor_id, source (those present) were lowercased, and also lowercased with domain suffixes (.com .io .org .net .dev .app .co .ai .api) stripped. A row counts if any column contains gitbook, baserow, looker, wekan, shortcut, clubhouse or bitrise as a substring.
2. Exact collision: python tuple (METHOD upper, path exact, summary exact after trim) against the same tuple built from the 1,821 exam #8 ops. Looser collision: (METHOD upper, path exact). Python tuples in sets, as in `r16/opkey.py`; no pandas hash of joined strings. Note an empty summary on both sides counts as equal, so exact collisions with empty summary are method+path collisions on ops that have no summary.
3. Our own keys, for the record: `opkey.k1` (method, path, operationId, summary) and `opkey.k2` (method, normalised path with {..} -> {}, lowercased, trailing slash dropped, operationId), run unchanged against the exam ops.

Which key r16 used against exam #8. None of these. r16 never compared op keys to the exam #8 ops. `r16/build_master_all.py` removed exam #8 vendors at spec level, before the pick: rwxmap's drop list (dc3a0e0, 260 specs / 4,680 ops, sha 75d5fc70...), plus our own name hits on the six vendors (`hits8`), plus same-sha256 mirrors, plus near-duplicate spec groups of those hits. K1 (and K2 for the dev overlap) was used only to dedupe against known r13/r15/dev rows. So the collisions below are not a drop-rule failure by construction; they are generic ops that appear in many vendors' specs.

## 1. Vendor/provider name matches

| file | rows | columns checked | rows matching a name |
|---|---|---|---|
| teacher-train-v3 | 360,536 | provider, vendor, source | 0 |
| set-A | 35,999 | provider, vendor, source | 0 |
| set-B | 60,177 | provider, vendor, source | 0 |
| round15-train (inherited) | 302,211 | provider, vendor | 41 |
| dev-v3 | 4,475 | vendor_id, source | 0 |

Distinct matching names (only the inherited file has any):

| file | column | term | value | rows | verdict |
|---|---|---|---|---|---|
| round15-train (inherited) | provider | clubhouse | clubhouseapi.com | 41 | name match on 'clubhouse'; see note |
| round15-train (inherited) | vendor | clubhouse | clubhouseapi | 41 | name match on 'clubhouse'; see note |

Note. All 41 rows are the old r13 source `clubhouseapi` (provider clubhouseapi.com), 41 rows with src r13 in round15/train. Its ops are the Clubhouse social-audio app's private API (/call_phone_number_auth, /check_waitlist_status, /create_channel, /follow ...), which is not Shortcut's API (Shortcut was formerly Clubhouse.io, the project tracker). So it is a name false positive in substance, but it is the match our PRD and rwxmap's alias list treat as the shortcut alias, and it was treated as a hit in r16: its 5 replay rows were already dropped from teacher-train-v3. teacher-train-v3, set A, set B and dev v3 hold 0 rows with any of the seven names (no true matches, no false positives). No row in any file has gitbook, baserow, looker, wekan, shortcut or bitrise in a vendor field, with or without domain suffix. The "inherited" 41 rows are in the r15 training data that the r16 models continue from; they are not in any r16-built file.

## 2. Collisions with exam #8 ops

Exam #8 has 1,821 ops. "Exam ops hit" is the number of distinct exam ops matched.

| file | rows | exact (method+path+summary): train rows | exam ops hit | looser (method+path): train rows | exam ops hit | k1 (with operationId): train rows | k2 (normalised, with operationId): train rows |
|---|---|---|---|---|---|---|---|
| teacher-train-v3 | 360,536 | 58 | 26 | 3,304 | 111 | 2 | 121 |
| set-A | 35,999 | 4 | 4 | 333 | 51 | 0 | 16 |
| set-B | 60,177 | 13 | 9 | 612 | 66 | 3 | 36 |
| round15-train (inherited) | 302,211 | 109 | 25 | 3,434 | 108 | 13 | 160 |
| dev-v3 | 4,475 | 0 | 0 | 53 | 29 | 0 | 4 |

Exact collisions are 0.016% (v3), 0.011% (A), 0.022% (B), 0.036% (inherited) of rows and 0 for dev. The inherited file is a different population from the three r16 files; do not add its numbers to theirs.

Generic versus specific. A collision is called generic when the path is a stock CRUD/auth route that many unrelated APIs carry (login, logout, users, user, projects, groups, folders, orgs, connections, roles, permissions, `/`); specific is anything else (vendor-flavoured resources). This is my judgement from the key table, not a rule.

### Exact collisions: teacher-train-v3

58 distinct train rows, 26 distinct keys; generic-route rows 50, specific-route rows 8 (a train row hitting two exam ops is counted once).

| key (method path summary) | kind | train ids | train vendors | exam ids | exam provider |
|---|---|---|---|---|---|
| POST /login `Login` | generic | r15-a9f9406fca27aed3, r15s-606c0fae2a5fdefa, r15s-9a16ed545628619a, r16-76b5f9383a2c8a6a, r16-7c8153d7460475cf, r16-a21691d993aaca7d, r16-ab24ee223a8af1b1, r16-e33bc954cb6cbf50 | agatha-budget.fr, discord.gg, imev-mer.fr, owner:suryaasaputra, title:abcstore, title:chatoffside, title:toshokanlearningplatform, xpry.com | ex8-1247 | looker.com |
| POST /projects `Create Project` | generic | ag-038172, r15-0c6806b419651e78, r15-2e91d1dee2888198, r16-200c30919bfff05c, r16-dc0a594495626835 | chicory.ai, files, thoughtfulgpt.com, title:simpleprofileprojectportfolio, workersense.com | ex8-1306 | looker.com |
| GET /api/users `` | generic | r15-544fdae58e4778fa, r16-3bba6e8bc13bf730, r16-44efa48ae72b35bd, r16-5d75a2bc46a7cfae, r16-d5bebb54f7ff9e0c | title:accessprovisioningandaudit, title:grncho, title:ohkamiworkerwith, title:omnitestbasicauth, title:youapp | ex8-1814 | wekan.github.io |
| GET /api/user `` | generic | r16-1ab6e8d28733cf9a, r16-a04ea4b849635394, r16-a3e3668621180382, r16-a7df29cbd632fa02, r16-cef509f2302914d8 | bardinpetr.ru, carbay.by, nordy.me, somewhere.com, title:webblock | ex8-1812 | wekan.github.io |
| POST /api/users `` | generic | r15s-270b5a2076c36200, r16-40ea0e9912d02520, r16-534a55e99b6bbdde, r16-671ca11623170075 | mynivo.com, title:accessprovisioningandaudit, title:dddcleantwitter, title:unifortrade | ex8-1815 | wekan.github.io |
| POST /groups `Create Group` | generic | r15-4bae3223380d2fc4, r15-73a6d704d9c9d27c, r16-6812ca11676c1e07 | 1msg.io, purpleair.com, title:flickweb | ex8-1205 | looker.com |
| POST /folders `Create Folder` | generic | r15c-c67ce6832b3ed7a9, r15c-d7c21d66620c1b93, r15s-5045dd5e7e680083 | media2url.com, namely.com, onna.com | ex8-1190 | looker.com |
| POST /users `Create User` | generic | ag-078370, r16-b42bed347e99bd66 | microsoft, owner:radnaeverdeni | ex8-1464 | looker.com |
| POST /connections `Create Connection` | generic | r15c-9e60a85a2dc9fc9a, r16-45e6d88d91e7c487 | title:affiliatematrix, withterminal.com | ex8-1075 | looker.com |
| POST /orgs `Create an organization` | generic | ag-039853, r16-5e2ecf4b74a52116 | alte-lms.tech, gitea | ex8-0685 | gitbook.com |
| PATCH /users/{user_id} `Update User` | generic | r16-0b723f838b56bd11, r16-5a4b1139b2e8c7e5 | farmacograph.org, title:smartbuy | ex8-1474 | looker.com |
| GET /api/jobs/ `` | specific | r16-3a19b02d201ad659, r16-7f0302429869ee12 | title:greenlit, title:hpcperfstats | ex8-0329 | baserow.io |
| GET / `Get API information` | generic | r16-627f083a61aa23d3, r16-b8df38c978d7b748 | title:aiecosystem, title:applytrack | ex8-0617 | gitbook.com |
| GET /builds `List all builds` | specific | r15-9b8c79ef09c92ac7 | imagefactory.io | ex8-0582 | bitrise.io |
| POST /agents `Create Agent` | specific | r15-b1a8238a4fbc1732 | kortix.com | ex8-1021 | looker.com |
| GET /roles `Get All Roles` | generic | r16-03867c83e48a5aea | title:nutrione | ex8-1368 | looker.com |
| GET /api/audit-log/ `` | specific | r16-0c2334bf3d825585 | title:sprintboard | ex8-0087 | baserow.io |
| GET /users/search `Search Users` | generic | r16-1ee910d929223e78 | title:chatterbox | ex8-1467 | looker.com |
| GET /permissions `Get All Permissions` | generic | r16-4555f58a7b0443e7 | owner:rahmatrafiq | ex8-1303 | looker.com |
| GET /api/applications/ `` | specific | r16-4f89405eea7c2374 | owner:thanvireddy25 | ex8-0079 | baserow.io |
| GET /api/admin/users/ `` | specific | r16-586531d63a56a14b | title:resqbite | ex8-0031 | baserow.io |
| PATCH /collections/{collectionId} `Update a collection` | specific | r16-59498b479c29d8a3 | title:schoolmoney | ex8-0622 | gitbook.com |
| DELETE /users/{user_id} `Delete User` | generic | r16-61fc4cb98a9ff5ed | clearshore.com | ex8-1472 | looker.com |
| DELETE /logout `Logout` | generic | r16-abfc65a7fa80991e | agatha-budget.fr | ex8-1249 | looker.com |
| POST /api/user/ `` | generic | r16-b601b04862d8c0a2 | title:itmoevents | ex8-0427 | baserow.io |
| GET /projects `Get All Projects` | generic | r16-ca81da32e98ea115 | title:simpleprofileprojectportfolio | ex8-1305 | looker.com |

### Exact collisions: set-A

4 distinct train rows, 4 distinct keys; generic-route rows 3, specific-route rows 1 (a train row hitting two exam ops is counted once).

| key (method path summary) | kind | train ids | train vendors | exam ids | exam provider |
|---|---|---|---|---|---|
| POST /projects `Create Project` | generic | r15-2e91d1dee2888198 | chicory.ai | ex8-1306 | looker.com |
| GET /api/users `` | generic | r16-5d75a2bc46a7cfae | title:grncho | ex8-1814 | wekan.github.io |
| GET /api/jobs/ `` | specific | r16-7f0302429869ee12 | title:hpcperfstats | ex8-0329 | baserow.io |
| DELETE /logout `Logout` | generic | r16-abfc65a7fa80991e | agatha-budget.fr | ex8-1249 | looker.com |

### Exact collisions: set-B

13 distinct train rows, 9 distinct keys; generic-route rows 12, specific-route rows 1 (a train row hitting two exam ops is counted once).

| key (method path summary) | kind | train ids | train vendors | exam ids | exam provider |
|---|---|---|---|---|---|
| POST /login `Login` | generic | r15-47467ca8f4b9e268, r15-adb6a59d8eff734e, r15-b684598caf043b3e, r15s-009bd7ea05191dcc | owner:darkiee12, pathfinder-software.com, title:mithras, title:xkcdhelper | ex8-1247 | looker.com |
| GET /api/users `` | generic | ag-036591, r16-5d75a2bc46a7cfae | drchrono, title:grncho | ex8-1814 | wekan.github.io |
| POST /users `Create User` | generic | ag-038229 | files | ex8-1464 | looker.com |
| POST /projects `Create Project` | generic | r15-2e91d1dee2888198 | chicory.ai | ex8-1306 | looker.com |
| POST /api/users `` | generic | r15-626cf62ba892af30 | title:ohkamiworkerwith | ex8-1815 | wekan.github.io |
| GET / `Get API information` | generic | r15-9b10b5ee891a3898 | kenny-agi.dev | ex8-0617 | gitbook.com |
| GET /api/user `` | generic | r15s-252186b66ef6ecbf | mynivo.com | ex8-1812 | wekan.github.io |
| GET /api/jobs/ `` | specific | r16-7f0302429869ee12 | title:hpcperfstats | ex8-0329 | baserow.io |
| DELETE /logout `Logout` | generic | r16-abfc65a7fa80991e | agatha-budget.fr | ex8-1249 | looker.com |

### Exact collisions: round15-train (inherited)

109 distinct train rows, 25 distinct keys; generic-route rows 99, specific-route rows 10 (a train row hitting two exam ops is counted once).

| key (method path summary) | kind | train ids | train vendors | exam ids | exam provider |
|---|---|---|---|---|---|
| POST /login `Login` | generic | ag-112372, r15-410a7476d3f81df3, r15-47467ca8f4b9e268, r15-60f945c17239dbd0, r15-6409462a789bb286, r15-782c32c9f0a9ea6d, r15-86d6febda755e1fe, r15-90392dc7abfb5cee, r15-a9f9406fca27aed3, r15-adb6a59d8eff734e, r15-b2378efc075ff006, r15-b507b017ad98bb65, r15-b684598caf043b3e, r15-d004a8b1dd95f1fe, r15s-009bd7ea05191dcc, r15s-033a871f7e0e0a24, r15s-21625929ad65762f, r15s-27afc3a1f0b57c73, r15s-3344beaf4ed93145, r15s-34953f3f63a3b61c, r15s-3c9c6730bddbc573, r15s-40984db09e35b7f6, r15s-4a183e1b371511ec, r15s-5078f2fb6a3daa5b, r15s-606c0fae2a5fdefa, r15s-64773da23be98693, r15s-6f0faa09770fe801, r15s-8273631cc78e58bf, r15s-85f9f4076ef27859, r15s-874699576e682303, r15s-9a16ed545628619a, r15s-a0529ba753f6f6c5, r15s-a085963f6f48f2fd, r15s-a087483eb1accc1c, r15s-a18dd513c53ecd2f, r15s-a344492c6f37aa77, r15s-ac87e9758b9f093f, r15s-e8adfb7cdcfb2d2e | alterra.id, araltech.tech, avisi.nl, axway.com, bluedevice.net, competa.com, crawlab.cn, cubes.com.ua, danobatgroup.com, discord.gg, erickmaster.me, fades.ge, fduhole.com, hcplataformapuma.com, minnis.com.br, monstar-lab.vn, owner:abdulkarim1422, owner:darkiee12, owner:dedyf5, owner:micbun, owner:spreee, owner:suryaasaputra, owner:tekishoinfotech, pathfinder-software.com, satanghq.com, searchbooster.io, sinao, sitefuelusa.com, title:filemanagement, title:goapp, title:mithras, title:platinumfuse, title:sweepaypos, title:xkcdhelper, undernet.org, uni-due.de, xpry.com, zapnito.com | ex8-1247 | looker.com |
| GET / `Get API information` | generic | r15-11b7948f501e8a82, r15-11d9850574175df2, r15-698c6513fa77a15c, r15-83d3b9d0eac35f7c, r15-9b10b5ee891a3898, r15-9d5553c8da337b61, r15-b0e9a83d7dbf0efe, r15-b551f111684b8636, r15-baa8419cde15fe7c, r15-bf8bb8f13340bad3, r15-cea0bc5c784e37f1, r15-d411029b76c7151d, r15-eeab0ca4dc5ccfcb, r15-f4a338e8b93f788d, r15-fce41ea1c9a42249 | doyle.la, gotak.app, kenny-agi.dev, production.com, title:authenticationgateway, title:baseacl, title:evently, title:genscan, title:megabankpaymentgateway, title:mockbanking, title:neurosymbolicaimarketsignalsplatform, title:ros2console, title:storybuilder, title:whatsappprivatemessagingservice, title:xratecosystem | ex8-0617 | gitbook.com |
| GET /api/users `` | generic | ag-036591, ag-120051, r15-099db081cd9a9c69, r15-25a1936aa7ac425c, r15-544fdae58e4778fa, r15-9e45677d82ceb6d9, r15s-38871f9ae69c08cc, r15s-bd3b978b9208e2a8 | acpdecisions.org, drchrono, owner:kaguya154, owner:usememos, title:groupmanager, title:ohkamiworkerwith, vocadb, xzevn.com | ex8-1814 | wekan.github.io |
| POST /users `Create User` | generic | ag-017448, ag-038229, ag-078370, r15-ae15294214680a8e, r15s-9a102527fb4bd4eb, r15s-de36a711c21a2ce0, r15s-e7e005e0a93c3ac2 | appwrite, connectiverx.com, files, fitnesshub.com, microsoft, title:laravelrobust, title:svnlusermanagement | ex8-1464 | looker.com |
| GET /api/user `` | generic | r15-00c671ceaedb02a4, r15-0694f685239604dc, r15-1b0f537eb68b1347, r15-ba95d01f15e571dd, r15s-252186b66ef6ecbf, r15s-66c2d0fa28ebed04 | mynivo.com, owner:bolehngopi, owner:malus2077, royalafg.games, superbikescentral.online, unige.ch | ex8-1812 | wekan.github.io |
| POST /api/users `` | generic | r15-037a4fd4d0817b19, r15-626cf62ba892af30, r15-d7a57421770835c1, r15s-270b5a2076c36200, r15s-a54969f3ab950104 | mynivo.com, owner:kaguya154, owner:mrfost07, title:ohkamiworkerwith, xzevn.com | ex8-1815 | wekan.github.io |
| POST /groups `Create Group` | generic | ag-038113, r15-4bae3223380d2fc4, r15-73a6d704d9c9d27c | 1msg.io, files, purpleair.com | ex8-1205 | looker.com |
| POST /projects `Create Project` | generic | ag-038172, r15-0c6806b419651e78, r15-2e91d1dee2888198 | chicory.ai, files, thoughtfulgpt.com | ex8-1306 | looker.com |
| DELETE /logout `Logout` | generic | r15s-46acfa3fcb6b1fd3, r15s-8ddc4c8992b4c3ae, r15s-cfbee83cf591ec85 | brapi.org, title:assetsyncmanagerbackend, title:miniprojectvocasia | ex8-1249 | looker.com |
| POST /folders `Create Folder` | generic | r15c-c67ce6832b3ed7a9, r15c-d7c21d66620c1b93, r15s-5045dd5e7e680083 | media2url.com, namely.com, onna.com | ex8-1190 | looker.com |
| POST /orgs `Create an organization` | generic | ag-039853, ag-063095 | gitea, influxdata | ex8-0685 | gitbook.com |
| POST /alerts `Create an alert` | specific | r15-58fca4532bf190f2, r15s-c7e48c98e21d4cf8 | gouze.io, livesession.io | ex8-1028 | looker.com |
| GET /agents/{agent_id} `Get Agent` | specific | r15-1d5a1d87a2226fff, r15-2d01ff51b6a1991e | title:quadracodeagentregistry, title:societas | ex8-1024 | looker.com |
| DELETE /alerts/{alert_id} `Delete an alert` | specific | ag-111415 | sendgrid | ex8-1030 | looker.com |
| GET /projects/{project_id} `Get Project` | generic | r15-3291743b9d6400d0 | chicory.ai | ex8-1307 | looker.com |
| DELETE /spaces/{spaceId} `Delete a space` | specific | r15-433450b5a3731036 | contentful.com | ex8-0916 | gitbook.com |
| PATCH /agents/{agent_id} `Update Agent` | specific | r15-1300cb0486c316c6 | deeptrail.com | ex8-1025 | looker.com |
| GET /builds `List all builds` | specific | r15-9b8c79ef09c92ac7 | imagefactory.io | ex8-0582 | bitrise.io |
| POST /agents `Create Agent` | specific | r15-b1a8238a4fbc1732 | kortix.com | ex8-1021 | looker.com |
| GET /users `Get All Users` | generic | r15s-11d093b93d080194 | lab8.com | ex8-1463 | looker.com |
| DELETE /groups/{group_id} `Delete Group` | generic | r15-6eff073dd52ee56c | purpleair.com | ex8-1209 | looker.com |
| DELETE /collections/{collectionId} `Delete a collection` | specific | r15-019b119d1d984b14 | semafind.com | ex8-0620 | gitbook.com |
| GET /user `Get Current User` | generic | r15s-ebf809cb63af360e | simpliship.xyz | ex8-1449 | looker.com |
| DELETE /users/{user_id} `Delete User` | generic | r15-314b7e624193e6c8 | title:bankingapplication | ex8-1472 | looker.com |
| POST /connections `Create Connection` | generic | r15c-9e60a85a2dc9fc9a | withterminal.com | ex8-1075 | looker.com |

Train ids are as in the file's id column (op_id for dev). Train vendor is the file's vendor column; exam provider is the provider column of ops.csv. No labels on either side.

## Summary

No r16-built file (teacher-train-v3, set A, set B, dev v3) holds any row whose vendor, provider, vendor_id or source names gitbook, baserow, looker, wekan, shortcut, clubhouse or bitrise. The inherited r15 train has 41 rows from `clubhouseapi` (the Clubhouse social-audio app, a name match on the old Shortcut name but a different product). Op-level, teacher-train-v3 shares 58 rows with exam #8 on exact method+path+summary (26 keys, 26 exam ops; 50 rows generic routes such as POST /login, GET /api/users, POST /projects; 8 rows vendor-flavoured but from unrelated vendors, e.g. GET /api/jobs/ and GET /api/audit-log/ against baserow) and 3,304 rows on method+path alone (111 exam ops). None of the colliding train rows comes from an exam #8 vendor. r16 removed exam #8 vendors at spec level (rwxmap's dc3a0e0 drop list plus our name hits, sha mirrors and near-duplicate groups), not by op key.
