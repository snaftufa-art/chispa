#!/usr/bin/env python3
"""Play-through test for Chispa: plays the app like a person (tapping and typing) and checks the data.

usage:  python3 -u tools/test_play.py /path/to/chispa [--save BACKUP] [--full] [--only NAME,...]

  --save BACKUP  start from a real save: a file with a CHISPA1:... backup code, a .txt backup, or state JSON.
                 Rule #1: before publishing, run this with a save from the current live version.
  --full         play the WHOLE course (all units, Temas, Más frases; about 15-20 min). Default: 25 sessions.
  --only         run only some parts: data, play, town, doors, features

Needs: pip install playwright, and Chrome/Chromium (set CHROME=/path/to/chrome if it isn't /usr/bin/google-chrome).
Exit code 1 if anything failed. Uses port 8799.
"""
import asyncio, base64, gzip, json, os, subprocess, sys, time
from playwright.async_api import async_playwright

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '.')
ARGS = sys.argv[1:]
def arg(name):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else None
FULL = '--full' in ARGS
ONLY = (arg('--only') or 'data,play,town,doors,features').split(',')
PORT = 8799; URL = f'http://127.0.0.1:{PORT}/'
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'play_helpers.js')
CHROME = os.environ.get('CHROME', '/usr/bin/google-chrome')

def load_save(path):
    if not path: return None
    t = open(path, encoding='utf-8').read().strip()
    if 'CHISPA1:' in t:
        code = t[t.index('CHISPA1:') + 8:].split()[0]
        return gzip.decompress(base64.b64decode(code)).decode('utf-8')
    json.loads(t); return t

SAVE = load_save(arg('--save'))

# ---------------- scenarios (run inside the page) ----------------
DATA = r"""(async () => {
  const bad = [], info = [];
  // conversations: flags given, waits, reachable NPCs
  const gives = {}; Object.entries(CONVS).forEach(([id, c]) => { if (c.give) gives[c.give] = 1; });
  const talkers = {}; NPCS.forEach(n => n.talks.forEach(t => talkers[t] = 1));
  Object.entries(CONVS).forEach(([id, c]) => { if (c.need && !gives[c.need]) bad.push(`conv ${id}: needs '${c.need}' that nobody gives`); if (!talkers[id]) bad.push(`conv ${id}: nobody says it`); });
  NPCS.forEach(n => n.talks.forEach(t => { if (!CONVS[t]) bad.push(`npc ${n.id}: unknown conv ${t}`); }));
  TOWN_QUESTS.forEach(([q, steps]) => steps.forEach(s => { if (!CONVS[s[1]]) bad.push(`quest ${q}: unknown conv ${s[1]}`); }));
  // audio for every spoken line
  let miss = 0; const chk = t => { if (t && !Voice.clip(t)) { miss++; if (miss < 6) bad.push('no recording: ' + t); } };
  Object.values(ITEMS).forEach(it => { if (it.u !== 300 && it.t !== 'p') chk(it.es); }); // 'p' = grammar puzzles: labels, never spoken
  if (typeof GRAM !== 'undefined') GRAM.forEach(G => G.ex.forEach(e => chk(gSay(e[0]))));
  Object.values(SCENES).forEach(sc => sc.l.forEach(l => chk(l[1])));
  Object.values(CONVS).forEach(c => c.l.forEach(l => l[0] === 'c' ? l[1].forEach(o => chk(o[0])) : chk(l[1])));
  if (miss) bad.push(`${miss} lines without recording`);
  // gap exercises
  [...COURSE, ...EXTRA].forEach(U => U.g.forEach(([s, a, d]) => { if (!s.includes('___')) bad.push(`gap without ___: ${s}`); if (d.split('|').some(x => norm(x) === norm(a))) bad.push(`gap option = answer: ${s}`); }));
  // buildings: every gate points at a real unit, prices set
  Object.entries(PLACES).forEach(([id, p]) => { if (p.b && p.b.cost && p.b.need && !COURSE[p.b.need - 1]) bad.push(`building ${id}: gate unit ${p.b.need} missing`); });
  // every NPC reachable with the game's own pathfinding
  const entries = {calle: [12, 11], playa: [4, 5], barrio: [10, 14]}, DIRS = {up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0]}, COUNTER = new Set(['C', 'F', 'M', 'I', 'Q']);
  const keep = JSON.stringify(ST); Object.entries(PLACES).forEach(([id, p]) => { if (p.b && p.b.cost) ST.built[id] = 1; });
  for (const [id, p] of Object.entries(PLACES)) {
    if (!p.rows) continue; const [ex, ey] = entries[id] || [4, 7];
    closeScreen(); ST.rpg.map = id; ST.rpg.x = ex; ST.rpg.y = ey; RPG.open(); await new Promise(r => setTimeout(r, 20)); const d = RPG._dbg();
    for (const n of d.npcs) { const spots = []; for (const k in DIRS) { const [ax, ay] = DIRS[k], x1 = n.x + ax, y1 = n.y + ay; if (!d.blocked(x1, y1)) spots.push([x1, y1]); else if (COUNTER.has((d.M.rows[y1] || '')[x1]) && !d.blocked(n.x + 2 * ax, n.y + 2 * ay)) spots.push([n.x + 2 * ax, n.y + 2 * ay]); }
      if (!spots.some(([x, y]) => (x === d.P.x && y === d.P.y) || d.bfs(x, y))) bad.push(`${id}: ${n.id} can't be reached`); }
  }
  closeScreen(); ST = JSON.parse(keep);
  info.push(`${Object.keys(ITEMS).length} items, ${Object.keys(CONVS).length} conversations, ${NPCS.length} people, ${Object.keys(AUDIO.c).length} clips`);
  return {bad, info};
})()"""

PLAY = r"""(async () => {
  await AP.sleep(300); await AP.closeModals(); const info = []; let n = 0, lastU = ST.open;
  const keys0 = keysEarned(), spent0 = ST.keysSpent || 0;
  while (n < %MAX%) {
    go('camino'); const lab = document.querySelector('#go small').textContent; if (/^Rayo/.test(lab)) break;
    const r = await AP.seguir('mixed'); n++;
    if (!r.end) { AP.issue('session did not finish', r.label); break; }
    if (ST.open !== lastU) { info.push(`unit ${ST.open} open after ${n} sessions · keys ${keysEarned()} · level ${lvlInfo(ST.xp).L}`); lastU = ST.open; }
    if (keysEarned() < keys0 || keysEarned() < spent0) AP.issue('keys went down', keysEarned());
  }
  info.push(`${n} sessions · units done ${[...COURSE, ...EXTRA].filter(U => unitDone(U.id)).length} · bonus ${Object.keys(ST.bonus).length} · grammar cards ${typeof gramDone === 'function' ? gramDone() : '-'}`);
  return {bad: AP.log.map(x => x.kind + ': ' + x.detail), info};
})()"""

TOWN = r"""(async () => {
  await AP.sleep(300); await AP.closeModals(); const D = TW.D, entry = {calle: [12, 11], playa: [4, 5], barrio: [10, 14]}, bad = [];
  Object.entries(PLACES).forEach(([id, p]) => { if (p.b && p.b.cost) ST.built[id] = 1; });
  await TW.enterMapAt('casa', 5, 6);
  for (const n of NPCS) { const pc = D().pickConv(n); if (pc.wait) { D().talk(n); await AP.sleep(30); const rn = document.querySelector('#rn'); if (!rn) bad.push('wait line without Continuar: ' + n.id); else AP.click(rn); await AP.sleep(30); if (D().talking) bad.push('stuck after wait line: ' + n.id); } }
  for (let pass = 0; pass < 30; pass++) { let any = false;
    for (const n of NPCS) { const pc = D().pickConv(n); if (!pc.fresh) continue; await TW.enterMapAt(n.map, ...(entry[n.map] || [4, 7])); const id = await TW.talkTo(n.id); any = true; if (!ST.rpg.done[id]) bad.push('not marked done: ' + id); }
    if (!any) break; }
  if (RPG.doneCount() !== RPG.total()) bad.push(`only ${RPG.doneCount()}/${RPG.total()} conversations reachable`);
  for (const id of ['lucia', 'samir']) { const m = NPCS.find(n => n.id === id).map; await TW.enterMapAt(m, ...(entry[m] || [4, 7])); await TW.talkTo(id); await TW.talkTo(id); }
  closeScreen();
  return {bad: bad.concat(AP.log.map(x => x.kind + ': ' + x.detail)), info: [`${RPG.doneCount()}/${RPG.total()} conversations, goal: ${RPG.nextGoal()}`]};
})()"""

DOORS = r"""(async () => {
  await AP.sleep(300); await AP.closeModals(); const D = TW.D, bad = [], info = [];
  for (const [id, p] of Object.entries(PLACES)) {
    if (!p.b) continue; const on = p.b.on || 'calle', dx = p.b.x + Math.floor(p.b.w / 2), dy = p.b.y + p.b.h - 1;
    await TW.enterMapAt(on, dx, dy + 1);
    const r = await TW.walkTo(dx, dy, 6000);
    if (r === 'modal') { const locked = p.b.cost && !ST.built[id]; if (!locked) bad.push(`${id}: unexpected dialog`); await AP.closeModals(); await AP.sleep(250); continue; }
    if (!r.startsWith('map:')) { bad.push(`${id}: door gave ${r}`); continue; }
    if (p.b.travel) { if (D().M.id !== p.b.travel[0]) bad.push(`${id}: travel went to ${D().M.id}`); continue; }
    if (D().M.id !== id) { bad.push(`${id}: entered ${D().M.id}`); continue; }
    let dd = null; D().M.rows.forEach((row, y) => { const x = row.indexOf('D'); if (x >= 0 && !dd) dd = [x, y]; });
    const back = await TW.walkTo(dd[0], dd[1], 8000);
    if (!(D().M.id === on && D().P.x === dx && D().P.y === dy + 1)) bad.push(`${id}: came out at ${D().M.id} ${D().P.x},${D().P.y} (${back})`);
  }
  closeScreen(); info.push('all doors walked'); return {bad, info};
})()"""

FEATURES = r"""(async () => {
  await AP.sleep(300); await AP.closeModals(); const bad = [], info = [], {click, sleep} = AP;
  for (const t of ['camino', 'entrenar', 'temas', 'progreso']) { go(t); if (document.querySelector('#view').innerText.length < 200) bad.push('tab looks empty: ' + t); }
  const code = await packState(), back = await unpackState(code);
  if (JSON.stringify({...back, upd: 0, backup: 0}) !== JSON.stringify({...ST, upd: 0, backup: 0})) bad.push('backup code does not restore the same progress');
  const old = Store.fix({xp: 500, items: {}, prog: {1: 5}, open: 2, gems: 20, rpg: {map: 'calle', x: 12, y: 11, done: {comida: 1}}, st: {lessons: 4}});
  const keep = ST; ST = old; try { for (const t of ['camino', 'entrenar', 'temas', 'progreso']) go(t); RPG.open(); await sleep(60); closeScreen(); } catch (e) { bad.push('old save breaks: ' + e); } ST = keep; go('camino');
  // double taps must not skip exercises
  startSession('lesson', {u: 1, node: 0, q: [exPick('w|hola', 'es2en'), exPick('w|adiós', 'es2en'), exPick('w|gracias', 'es2en')]});
  let ex = S.q[0]; click([...document.querySelectorAll('.opt')].find(x => x.dataset.v === ex.ans)); click(document.querySelector('#ck')); await sleep(20);
  const nx = document.querySelector('#lnext'); click(nx); await sleep(50); click(nx); if (S.i !== 1) bad.push('double tap on Continuar skipped an exercise'); closeScreen(); S = null;
  startSession('lesson', {u: 1, node: 0, q: [exRecall('w|hola'), exPick('w|adiós', 'es2en'), exPick('w|gracias', 'es2en')]});
  click(document.querySelector('#show')); await sleep(10); const r2 = document.querySelector('#r2'); click(r2); await sleep(60); click(r2); await sleep(600);
  if (!S || S.i !== 1) bad.push('double tap on ¡Lo sabía! skipped an exercise'); closeScreen(); S = null;
  // dictionary
  await Dict.load();
  const want = {no: 'no', buena: 'bueno', fui: 'ir', 'sé': 'saber', vosotros: 'vosotros', trabajo: 'trabajar', 'España': 'España', cat: 'gato', tengo: 'tener', resfriada: 'resfriado', house: 'casa'};
  for (const [q, w] of Object.entries(want)) { const r = Dict.search(q), all = [...r.es, ...r.en].map(x => Dict.data.D[x.i][0]); if (!all.includes(w)) bad.push(`dictionary: "${q}" doesn't find ${w} (got ${all.slice(0, 3).join(', ') || 'nothing'})`); }
  if (/letter/.test(Dict.short(Dict.data.D.findIndex(e => e[0] === 'de')))) bad.push('dictionary: "de" shows the letter first');
  // a dictionary word without recording gets no listening exercise when the phone can't speak
  ST.custom = Object.assign({}, ST.custom, {ardilla: 'squirrel'}); registerCustom();
  if (!canHear('ardilla')) for (let i = 0; i < 40; i++) { const t = ladder('w|ardilla').type; if (['lmean', 'listen', 'dict', 'lbuild'].includes(t)) { bad.push('silent listening exercise for a word without sound: ' + t); break; } }
  delete ST.custom.ardilla; delete ST.items['w|ardilla'];
  // Rayo
  startRayo(); await sleep(150); click(document.querySelector('#rx')); await sleep(100); await AP.closeModals(); await sleep(100);
  info.push('backup, old save, double taps, dictionary, Rayo checked');
  return {bad: bad.concat(AP.log.map(x => x.kind + ': ' + x.detail)), info};
})()"""

async def run(pw, name, js, timeout_ms):
    b = await pw.chromium.launch(executable_path=CHROME, args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
    ctx = await b.new_context(viewport={'width': 400, 'height': 860}, service_workers='block')
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(f'page error: {e}'))
    pg.on('console', lambda m: errs.append(f'console: {m.text}') if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    if SAVE:
        await pg.add_init_script(f"if (!sessionStorage.getItem('seeded')) {{ localStorage.setItem('chispa.v2', {json.dumps(SAVE)}); sessionStorage.setItem('seeded', '1'); }}")
    await pg.goto(URL); await pg.wait_for_timeout(700)
    await pg.add_script_tag(path=HELPERS)
    t0 = time.time()
    try:
        r = await asyncio.wait_for(pg.evaluate(js), timeout_ms / 1000)
    except Exception as e:
        r = {'bad': [f'{name} crashed: {e}'], 'info': []}
    await b.close()
    bad = r['bad'] + errs
    print(f"\n== {name} ({time.time() - t0:.0f}s): {'OK' if not bad else str(len(bad)) + ' problem(s)'}")
    for i in r['info']: print('   ' + i)
    for x in bad[:40]: print('   ✗ ' + x)
    return not bad

async def main():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); ok = True
    print(f'Chispa test · {ROOT} · save: {arg("--save") or "new player"} · {"full course" if FULL else "quick"}')
    try:
        async with async_playwright() as pw:
            if 'data' in ONLY: ok &= await run(pw, 'data', DATA, 120000)
            if 'features' in ONLY: ok &= await run(pw, 'features', FEATURES, 120000)
            if 'doors' in ONLY: ok &= await run(pw, 'doors', DOORS, 300000)
            if 'town' in ONLY: ok &= await run(pw, 'town', TOWN, 900000)
            if 'play' in ONLY: ok &= await run(pw, 'play', PLAY.replace('%MAX%', '700' if FULL else '25'), 3600000)
    finally:
        srv.terminate()
    print('\nALL OK' if ok else '\nSOME CHECKS FAILED')
    sys.exit(0 if ok else 1)

asyncio.run(main())
