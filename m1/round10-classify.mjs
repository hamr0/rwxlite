// Round 10 helper: classify rows with CURRENT rwxmap (classifyRow). stdin: JSON array of
// {method,path,operationId,summary,description}; stdout: JSON array of {class,rule}.
// rwxmap checkout at ../rwxmap or $RWXMAP_DIR (same loading as m0/exam-inputs.mjs). No network, no Jev.
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const RWXMAP = process.env.RWXMAP_DIR || path.resolve(HERE, '..', '..', 'rwxmap');
const { classifyRow } = await import(pathToFileURL(path.join(RWXMAP, 'src', 'index.js')).href);
const rows = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(rows.map((r) => { const v = classifyRow(r); return { class: v.class, rule: v.rule }; })));
