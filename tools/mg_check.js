// Lists the town minigame lines (Busca a Wilma, Turno en Kebab Luna, Noche de bienvenida) and which have no audio.
// usage: node tools/mg_check.js index.html [--all out.json]
const fs = require('fs'), [, , file = 'index.html', flag, out] = process.argv;
const s = fs.readFileSync(file, 'utf8');
const a = s.indexOf('/* ================= Minijuegos del pueblo: data'), f = s.indexOf('function MG_LINES()', a), b = s.indexOf('\n}\n', f) + 3;
if (a < 0 || f < 0) { console.error('minigame data not found'); process.exit(1); }
const AUDIO = JSON.parse(s.match(/const AUDIO = (\{.*?\});\n/)[1]);
const stub = "const NPCS = [{id: 'wilma'}, {id: 'tormenta'}], ITEMS = {}, UNIT_KEYS = {200: {s: []}};\n";
const m = {exports: {}}; new Function('module', stub + s.slice(a, b) + '\nmodule.exports = {MG_LINES, HIDE_SPOTS, KB_ORDERS, BV_GUESTS};')(m);
const all = m.exports.MG_LINES(), need = all.filter(([v, t]) => !AUDIO.c[v + '|' + t]);
console.log(`${all.length} minigame lines, ${need.length} without audio · ${m.exports.HIDE_SPOTS.length} hiding spots · ${m.exports.KB_ORDERS.length} orders · ${m.exports.BV_GUESTS.length} guests`);
need.slice(0, 20).forEach(([v, t]) => console.log('  missing', v, t));
if (flag === '--all') fs.writeFileSync(out, JSON.stringify(all));
