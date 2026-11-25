// Checks the grammar data block in index.html (or a separate file) and lists which lines still need audio.
// usage: node gram_check.js <file with the GRAM block> [index.html for the AUDIO manifest]
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const html = fs.readFileSync(process.argv[3] || process.argv[2], 'utf8');
const block = src.slice(src.indexOf('/* ================= Gramática: Wilma explica (data)'), src.indexOf('/* ================= end Gramática data'));
const G = new Function(block + '; return {GRAM, gramLines, gFix, gSay, gSortSay, GRAM_WSAY};')();
const AUDIO = JSON.parse(html.match(/const AUDIO = (\{.*?\});\n/)[1]);
const errs = [];
const units = new Set();
for (const g of G.GRAM) {
  const e = m => errs.push(g.id + ': ' + m);
  if (units.has(g.u)) e('duplicate unit'); units.add(g.u);
  if (g.id !== 'g' + g.u) e('id should be g' + g.u);
  if (g.ex.length < 3) e('needs 3+ examples');
  g.ex.forEach(x => { if (!/\{.+?\}/.test(x[0])) e('example without {pink}: ' + x[0]); if ((x[0].match(/\{/g) || []).length !== (x[0].match(/\}/g) || []).length) e('braces: ' + x[0]); });
  if (!g.ask || g.ask[1].length !== 3) e('ask needs 3 options');
  if (!g.rule || !g.de || !g.tab.length) e('rule/de/tab missing');
  const types = g.p.map(p => p[0]).join(',');
  if (types !== 'sort,gap,gap,fix') e('puzzle order ' + types);
  for (const p of g.p) {
    if (p[0] === 'sort') {
      if (p[2].length < 2 || p[2].length > 3) e('sort buckets');
      p[3].forEach(it => { if (it[1] >= p[2].length) e('bucket index ' + it[0]); if (it[0].includes('…') && !it[2]) e('sort item needs spoken form: ' + it[0]); });
      p[2].forEach((b, i) => { if (!p[3].some(it => it[1] === i)) e('empty bucket ' + b); });
      if (!p[4]) e('sort why missing');
    } else if (p[0] === 'gap') {
      if ((p[1].match(/___/g) || []).length !== 1) e('gap needs one ___: ' + p[1]);
      if (p[3].split('|').includes(p[2])) e('answer among distractors: ' + p[1]);
      if (!p[5]) e('gap why missing');
    } else if (p[0] === 'fix') {
      const f = G.gFix(p);
      if (f.wi < 0) e('fix word not found: ' + p[1]);
      if (p[4].split('|').includes(p[3]) || p[4].split('|').includes(p[2])) e('fix distractors overlap: ' + p[1]);
      if (f.full === p[1]) e('fix changes nothing');
      if (!p[6]) e('fix why missing');
    }
  }
}
const lines = G.gramLines();
const have = new Set(Object.keys(AUDIO.c));
const need = lines.filter(([v, t]) => !have.has(v + '|' + t));
const uniqNeed = [...new Map(need.map(l => [l[0] + '|' + l[1], l])).values()];
console.log(errs.length ? 'ERRORS:\n' + errs.join('\n') : 'data ok');
console.log(`patterns ${G.GRAM.length} · lines ${lines.length} · already recorded ${lines.length - need.length} · to synthesize ${uniqNeed.length}`);
if (process.argv.includes('--fixes')) G.GRAM.forEach(g => g.p.filter(p => p[0] === 'fix').forEach(p => console.log(g.id, '|', p[1], '→', G.gFix(p).full)));
if (process.argv.includes('--need')) uniqNeed.forEach(l => console.log(l.join(' | ')));
if (process.argv.includes('--json')) fs.writeFileSync(process.argv[process.argv.indexOf('--json') + 1], JSON.stringify(uniqNeed));
if (process.argv.includes('--all')) fs.writeFileSync(process.argv[process.argv.indexOf('--all') + 1], JSON.stringify([...new Map(lines.map(l => [l[0] + '|' + l[1], l])).values()]));
process.exit(errs.length ? 1 : 0);
