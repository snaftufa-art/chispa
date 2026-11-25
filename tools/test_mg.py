"""Headless test of the town minigames (Busca a Wilma, Turno en Kebab Luna, Noche de bienvenida) and of old saves.
usage: python3 -u tools/test_mg.py /path/to/chispa [old_ref=origin/main] [shots_dir=/tmp/mgshots]
Serves the old version (git show <old_ref>:index.html) at /old/ and the working copy at /new/ on one origin:
builds progress in the old one, checks the new one reads it the same, then plays all three games and some conversations.
Needs playwright and /usr/bin/google-chrome."""
import asyncio, json, os, sys, threading, functools, http.server, socketserver, subprocess, tempfile
from playwright.async_api import async_playwright
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.'); OLD = sys.argv[2] if len(sys.argv) > 2 else 'origin/main'
SHOTS = sys.argv[3] if len(sys.argv) > 3 else '/tmp/mgshots'; PORT = 8766
os.makedirs(SHOTS, exist_ok=True)
ROOT = tempfile.mkdtemp(prefix='chispa_mg_'); os.symlink(REPO, os.path.join(ROOT, 'new')); od = os.path.join(ROOT, 'old'); os.mkdir(od)
for n in os.listdir(REPO):
    if n not in ('index.html', '.git'): os.symlink(os.path.join(REPO, n), os.path.join(od, n))
open(os.path.join(od, 'index.html'), 'w', encoding='utf-8').write(subprocess.run(['git', '-C', REPO, 'show', OLD + ':index.html'], capture_output=True, text=True, check=True).stdout)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.ThreadingTCPServer.allow_reuse_address = True
srv = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), functools.partial(Q, directory=ROOT)); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
ERR = []
def ok(c, msg):
    print(('PASS ' if c else 'FAIL ') + msg, flush=True)
    if not c: ERR.append(msg)

# click through whatever the town panel is showing until a condition holds
CLICK = """async (stopJs) => {
  const stop = new Function('return (' + stopJs + ')');
  for (let i = 0; i < 400; i++) {
    if (stop()) return i;
    const q = s => document.querySelector(s);
    const mb = q('.modal button.btn, .modal [data-close]'); if (mb) { mb.click(); await new Promise(r => setTimeout(r, 120)); continue; }
    const b = q('#rp #rn:not([disabled])') || q('#rp #rc:not([disabled])');
    if (b && !b.hidden) { b.click(); await new Promise(r => setTimeout(r, 60)); continue; }
    const tiles = [...document.querySelectorAll('#rz .bank .tile:not(.used)')];
    if (tiles.length) { tiles[0].click(); await new Promise(r => setTimeout(r, 20)); continue; }
    const opts = [...document.querySelectorAll('#rp .opt:not([disabled]):not(.right)')];
    if (opts.length) { opts[0].click(); await new Promise(r => setTimeout(r, 80)); continue; }
    const r2 = q('#rp #r2'); if (r2) { r2.click(); await new Promise(r => setTimeout(r, 60)); continue; }
    const rs = q('#rp #rs'); if (rs) { rs.click(); await new Promise(r => setTimeout(r, 60)); continue; }
    await new Promise(r => setTimeout(r, 100));
  }
  return -1;
}"""

async def dm(pg):
    for _ in range(5):
        if not await pg.evaluate("() => { const b = document.querySelector('.modal button.btn, .modal [data-close]'); if (b) { b.click(); return true; } return false; }"): return
        await pg.wait_for_timeout(150)

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, service_workers='block')
        pg = await ctx.new_page(); GP.append(pg)
        pg.on('pageerror', lambda e: ERR.append('pageerror: ' + str(e)) or print('PAGEERROR', e))
        pg.on('console', lambda m: m.type == 'error' and not 'Failed to load resource' in m.text and print('CONSOLE', m.text))

        # 1. make an old save with the published app
        await pg.goto(f'http://127.0.0.1:{PORT}/old/index.html'); await pg.wait_for_timeout(800)
        await pg.evaluate("""() => { ST.welcomed = 1; ST.backup = Date.now(); ST.xp = 5400; ST.gems = 333; ST.open = 12; ST.keysSpent = 3; ST.built = {metro: 1};
          ['hambre','comida','malita','medicina','lucia1','alex','noa','samir','paqui'].forEach(k => ST.rpg.done[k] = 1); ST.rpg.flags.need_food = 1; ST.rpg.flags.fed = 1; ST.rpg.flags.noa = 1; ST.rpg.pron = undefined;
          Object.keys(ITEMS).slice(0, 120).forEach((k, i) => ST.items[k] = [1 + i % 5, today() - (i % 3), 2, 0, 0]);
          ST.prog = {1: {l: 3, f: 1}, 2: {l: 3, f: 1}}; Store.save(); }""")
        old = await pg.evaluate("() => ({raw: localStorage.getItem('chispa.v2'), keys: keysFree(), earned: keysEarned(), done: RPG.doneCount(), total: RPG.total(), due: dueKeys().length, seen: seenKeys().length, xp: ST.xp, gems: ST.gems, goal: RPG.nextGoal(), badges: checkBadges().length})")
        raw = old.pop('raw')

        # 2. the new app reads it the same way
        await pg.goto(f'http://127.0.0.1:{PORT}/new/index.html'); await pg.wait_for_timeout(800)
        new = await pg.evaluate("() => ({keys: keysFree(), earned: keysEarned(), done: RPG.doneCount(), total: RPG.total(), due: dueKeys().length, seen: seenKeys().length, xp: ST.xp, gems: ST.gems, goal: RPG.nextGoal(), badges: checkBadges().length})")
        ok({k: v for k, v in old.items() if k != 'total'} == {k: v for k, v in new.items() if k != 'total'} and new['total'] >= old['total'], f'old save reads the same in the new app {new}')  # total grows when new conversations ship
        ok(await pg.evaluate("() => JSON.stringify(ST.mg) === '{}'"), 'old save gets an empty minigame record')
        miss = await pg.evaluate("() => MG_LINES().filter(([v, t]) => !AUDIO.c[v + '|' + t]).map(x => x.join('|'))")
        ok(not miss, f'every minigame line has recorded audio {miss[:5]}')
        f = await pg.evaluate("async () => { const fi = AUDIO.f.findIndex(x => x.startsWith('mg.')); const r = await fetch('audio/' + AUDIO.f[fi] + '.mp3'); return [r.status, (await r.arrayBuffer()).byteLength]; }")
        ok(f[0] == 200 and f[1] > 1000000, f'minigame audio file loads {f}')

        # 3. every hiding spot is free and reachable from your front door
        await pg.evaluate("() => RPG.open()"); await pg.wait_for_timeout(500)
        bad = await pg.evaluate("""() => { const d = RPG._dbg(); d.loadMap('calle', 4, 7, 'down'); const out = [];
          for (const s of HIDE_SPOTS) { const D = RPG._dbg(); if (D.blocked(s[0], s[1])) { out.push('blocked ' + s); continue; }
            const adj = [[0,1],[0,-1],[1,0],[-1,0]].map(([a,b]) => [s[0]+a, s[1]+b]).filter(([x,y]) => !D.blocked(x,y));
            if (!adj.some(([x,y]) => D.bfs(x, y) !== null) && D.bfs(s[0], s[1]) === null) out.push('unreachable ' + s); }
          return out; }""")
        ok(not bad, f'all {25} hiding spots free and reachable {bad}')

        # 4. Busca a Wilma
        await pg.evaluate("() => { const d = RPG._dbg(); d.loadMap('casa', 4, 5, 'up'); }"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const d = RPG._dbg(); d.talk(d.npcs.find(n => n.id === 'wilma')); }"); await pg.wait_for_timeout(400)
        ok(await pg.evaluate("() => !!document.querySelector('#mgp') && !!document.querySelector('#mgt')"), 'Wilma offers the game and a chat')
        await pg.screenshot(path=f'{SHOTS}/1_menu_wilma.png')
        await dm(pg); await pg.click('#mgp'); await pg.wait_for_timeout(300)
        await pg.evaluate(CLICK, "document.querySelector('#mgc')")
        ok(await pg.evaluate("() => !RPG._dbg().npcs.some(n => n.id === 'wilma')"), 'Wilma disappears to hide')
        await pg.wait_for_timeout(500); await pg.screenshot(path=f'{SHOTS}/2_count.png')
        await pg.wait_for_function("() => { const b = document.querySelector('#rn'); return b && !b.hidden; }", timeout=30000)
        await dm(pg); await pg.click('#rn'); await pg.wait_for_function("() => RPG._dbg().hide && RPG._dbg().hide.s", timeout=25000)
        ok(await pg.evaluate("() => !!document.querySelector('#mghide')"), 'clue bar shows the clue')
        spot = await pg.evaluate("() => RPG._dbg().hide.s")
        # walk out, stand 3 tiles away: tail visible, heat says hot
        await pg.evaluate("""(s) => { const d = RPG._dbg(); d.loadMap('calle', 4, 7, 'down');
          let best = null; for (let y = 1; y < 22; y++) for (let x = 1; x < 39; x++) { const m = Math.abs(x - s[0]) + Math.abs(y - s[1]); if (m === 3 && !d.blocked(x, y) && d.bfs(x, y)) best = best || [x, y]; }
          d.loadMap('calle', best[0], best[1], 'down'); RPG._dbg().arrive(); }""", spot)
        await pg.wait_for_timeout(400)
        heat = await pg.evaluate("() => document.querySelector('#mgheat').textContent")
        ok('Caliente' in heat or 'quemas' in heat, f'heat near Wilma: {heat}')
        await dm(pg); await pg.click('#mgh'); await pg.wait_for_timeout(200); await dm(pg); await pg.click('#mgh'); await pg.wait_for_timeout(200)
        ok(await pg.evaluate("() => document.querySelectorAll('#mghide small').length === 2"), 'two hints shown')
        await pg.screenshot(path=f'{SHOTS}/3_hide_clue.png')
        await pg.evaluate("""(s) => { const d = RPG._dbg(); const adj = [[0,1],[0,-1],[1,0],[-1,0]].map(([a,b]) => [s[0]+a, s[1]+b]).find(([x,y]) => !d.blocked(x,y));
          d.loadMap('calle', adj[0], adj[1], 'down'); RPG._dbg().arrive(); }""", spot)
        await pg.wait_for_timeout(500)
        ok(await pg.evaluate("() => RPG._dbg().hide && RPG._dbg().hide.found"), 'walking next to Wilma finds her')
        await pg.screenshot(path=f'{SHOTS}/4_found.png')
        await pg.evaluate(CLICK, "document.querySelector('#mgq')"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/5_end_wilma.png')
        await dm(pg); await pg.click('#mgq'); await pg.evaluate(CLICK, "document.querySelector('#ra')")
        st = await pg.evaluate("() => ({mg: ST.mg.escondite, hide: RPG._dbg().hide})")
        ok(st['mg']['plays'] == 1 and st['mg']['stars'] == 1 and st['hide'] is None, f'Wilma round recorded {st}')
        await pg.evaluate("() => RPG._dbg().loadMap('casa', 4, 5, 'up')")
        ok(await pg.evaluate("() => RPG._dbg().npcs.some(n => n.id === 'wilma')"), 'Wilma is back home')

        # 5. Turno en Kebab Luna (one timeout, one wrong, rest right)
        await pg.evaluate("() => { const d = RPG._dbg(); d.loadMap('kebab', 1, 3, 'up'); const D = RPG._dbg(); D.talk(D.npcs.find(n => n.id === 'luna')); }"); await pg.wait_for_timeout(300)
        ok(await pg.evaluate("() => !!document.querySelector('#mgp') && !document.querySelector('#mgt')"), 'Luna offers only the game')
        await dm(pg); await pg.click('#mgp'); await pg.evaluate(CLICK, "document.querySelector('.mgmenu')")
        await pg.wait_for_timeout(300); await pg.screenshot(path=f'{SHOTS}/6_kebab.png')
        for k in range(6):
            await pg.wait_for_selector('.mgmenu', timeout=10000)
            if k == 0:  # let the first customer run out of patience
                await pg.wait_for_selector('.mgfb', timeout=40000); txt = await pg.evaluate("() => document.querySelector('.mgfb').className"); ok('bad' in txt, 'customer leaves when patience runs out')
            else:
                await dm(pg); await pg.click('#mgtxt'); order = await pg.evaluate("() => document.querySelector('#mgo').textContent")
                items = await pg.evaluate("(o) => KB_ORDERS.find(x => x[1] === o)[3].split(' ')", order)
                if k == 2: items = items[:-1] + (['agua'] if items[-1] != 'agua' else ['te'])
                for it in items: await dm(pg); await pg.click(f'.mgitem[data-id="{it}"]')
                if k == 1: await pg.screenshot(path=f'{SHOTS}/7_kebab_tray.png')
                await dm(pg); await pg.click('#mgserve'); await pg.wait_for_selector('.mgfb')
                cls = await pg.evaluate("() => document.querySelector('.mgfb').className")
                ok(('good' in cls) == (k != 2), f'customer {k + 1}: {order} -> {cls}')
                if k == 2: await pg.screenshot(path=f'{SHOTS}/8_kebab_wrong.png')
            await pg.wait_for_selector('#rn'); await dm(pg); await pg.click('#rn')
        await pg.evaluate(CLICK, "document.querySelector('#mgq')"); await pg.screenshot(path=f'{SHOTS}/9_end_kebab.png')
        await dm(pg); await pg.click('#mgq'); await pg.wait_for_timeout(300)
        st = await pg.evaluate("() => ({mg: ST.mg.camarero, P: [RPG._dbg().P.x, RPG._dbg().P.y], extras: RPG._dbg().npcs.filter(n => n.mg).length, pad: !!document.querySelector('#ra')})")
        ok(st['mg']['plays'] == 1 and st['mg']['stars'] == 2 and st['P'] == [1, 3] and st['extras'] == 0 and st['pad'], f'kebab round recorded, you are back in front of the counter {st}')

        # 6. Noche de bienvenida: Tormenta's conversation first, then the game
        await pg.evaluate("() => { const d = RPG._dbg(); d.loadMap('bar', 7, 3, 'right'); const D = RPG._dbg(); D.talk(D.npcs.find(n => n.id === 'tormenta')); }"); await pg.wait_for_timeout(300)
        ok(await pg.evaluate("() => !document.querySelector('#mgp')"), 'new conversation with La Tormenta comes before the game')
        await pg.evaluate(CLICK, "document.querySelector('#ra')")
        ok(await pg.evaluate("() => ST.rpg.done.tormenta === 1"), 'La Tormenta conversation still completes')
        await pg.evaluate("() => { const d = RPG._dbg(); d.talk(d.npcs.find(n => n.id === 'tormenta')); }"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/10_menu_tormenta.png')
        await dm(pg); await pg.click('#mgp'); await pg.wait_for_timeout(200)
        # asked for your pronouns (none saved yet): pick elle
        await pg.evaluate(CLICK, "document.querySelector('#rz .opt[data-i]')")
        await dm(pg); await pg.click('#rz .opt[data-i="2"]'); await pg.wait_for_timeout(100)
        ok(await pg.evaluate("() => ST.rpg.pron === 2"), 'your pronoun is asked and saved')
        await pg.evaluate(CLICK, "document.querySelector('.mgtipcard')"); await pg.screenshot(path=f'{SHOTS}/11_tip.png')
        await dm(pg); await pg.click('#rn'); wrong_done = False; n_guests = 0
        while True:
            try: await pg.wait_for_function("() => document.querySelector('.mgbv') || document.querySelector('.mgend') || (document.querySelector('#rn') && !document.querySelector('.mgbv'))", timeout=25000)
            except Exception: print('STUCK A', (await pg.evaluate("() => document.querySelector('#rp').innerHTML"))[:900]); raise
            if await pg.evaluate("() => !document.querySelector('.mgbv')"): break
            if await pg.evaluate("() => !!document.querySelector('#rz .opt:not([disabled])')"):
                name = await pg.evaluate("() => document.querySelectorAll('.mgbv .rwho')[1].textContent")
                fx = await pg.evaluate("(n) => BV_GUESTS.find(g => g.n === n).fx", name)
                pickf = fx[0] if (wrong_done or n_guests < 1) else [f for f in [0, 1, 2] if f not in fx][0]
                if pickf not in fx: wrong_done = True
                if n_guests == 0: await pg.screenshot(path=f'{SHOTS}/12_guest.png')
                await dm(pg); await pg.click(f'#rz .opt[data-f="{pickf}"]'); await pg.wait_for_timeout(150)
                if pickf not in fx:
                    await pg.wait_for_selector('.mgsorry'); await pg.screenshot(path=f'{SHOTS}/13_sorry.png'); await dm(pg); await pg.click('.mgsorry')
                    try: await pg.wait_for_function("() => !document.querySelector('.mgsorry') || document.querySelector('#rl3')", timeout=25000)
                    except Exception: print('STUCK B', (await pg.evaluate("() => document.querySelector('#rp').innerHTML"))[:900]); raise
                try: await pg.wait_for_function("() => !document.querySelector('#rz .opt[disabled]')", timeout=25000)
                except Exception: print('STUCK C', (await pg.evaluate("() => document.querySelector('#rp').innerHTML"))[:900]); raise
                continue
            b = await pg.query_selector('.mgbv #rn:not([disabled]):not(.mgsorry)')
            if b: n_guests += 1; await b.click()
            await pg.wait_for_timeout(80)
        await pg.evaluate(CLICK, "document.querySelector('#mgq')"); await pg.screenshot(path=f'{SHOTS}/14_end_bv.png')
        await dm(pg); await pg.click('#mgq'); await pg.wait_for_timeout(300)
        st = await pg.evaluate("() => ({mg: ST.mg.bienvenida, P: [RPG._dbg().P.x, RPG._dbg().P.y], graded: Object.keys(ST.items).filter(k => Object.values(BV_STEP2).some(([f]) => f.some(e => 's|' + e === k))).length, extras: RPG._dbg().npcs.filter(n => n.mg).length})")
        ok(st['mg']['plays'] == 1 and st['mg']['best'] >= 12 and st['P'] == [7, 3] and st['graded'] >= 4 and st['extras'] == 0, f'welcome night recorded, phrases join review {st}')

        # 7. misiones lists the games; leaving mid-game is safe
        await dm(pg); await pg.click('#rm'); await pg.wait_for_timeout(200)
        ok(await pg.evaluate("() => document.querySelector('.modal').textContent.includes('Minijuegos')"), 'Misiones lists the minigames')
        await pg.screenshot(path=f'{SHOTS}/15_misiones.png'); await pg.evaluate("() => document.querySelector('.modal [data-close]').click()")
        await pg.evaluate("() => { const d = RPG._dbg(); d.loadMap('kebab', 1, 3, 'up'); const D = RPG._dbg(); D.talk(D.npcs.find(n => n.id === 'luna')); }"); await pg.wait_for_timeout(200)
        await dm(pg); await pg.click('#mgp'); await pg.evaluate(CLICK, "document.querySelector('.mgmenu')")
        await dm(pg); await pg.click('#rx'); await pg.wait_for_timeout(300); await pg.evaluate("() => RPG.open()"); await pg.wait_for_timeout(300)
        st = await pg.evaluate("() => ({map: RPG._dbg().M.id, P: [RPG._dbg().P.x, RPG._dbg().P.y], extras: RPG._dbg().npcs.filter(n => n.mg).length})")
        ok(st == {'map': 'kebab', 'P': [1, 3], 'extras': 0}, f'closing mid-game leaves you where you were {st}')

        # the published version can still read the new save (in case of a rollback) and keeps the minigame records
        before = await pg.evaluate("() => { Store.save(); return {xp: ST.xp, done: Object.keys(ST.rpg.done).length, mg: JSON.stringify(ST.mg)}; }")
        await pg.goto(f'http://127.0.0.1:{PORT}/old/index.html'); await pg.wait_for_timeout(800)
        after = await pg.evaluate("() => { Store.save(); return {xp: ST.xp, done: Object.keys(ST.rpg.done).length, mg: JSON.stringify(ST.mg)}; }")
        ok(before == after and after['mg'] != '{}', f'old version reads the new save and keeps the minigame records {after["xp"]} xp')
        await pg.goto(f'http://127.0.0.1:{PORT}/new/index.html'); await pg.wait_for_timeout(600)
        # 8. the classic conversations still work (fresh save, a sample across the town)
        await pg.evaluate("() => { localStorage.clear(); }"); await pg.goto(f'http://127.0.0.1:{PORT}/new/index.html'); await pg.wait_for_timeout(600)
        await pg.evaluate("() => { ST.welcomed = 1; ST.backup = Date.now(); Store.save(); document.querySelectorAll('.modal').forEach(m => m.remove()); }")
        await pg.evaluate("() => RPG.open()"); await pg.wait_for_timeout(300)
        for nid in ['wilma', 'paqui', 'wilma', 'lucia', 'alex', 'noa', 'samir', 'iker', 'carmen', 'tormenta']:
            r = await pg.evaluate("""async (nid) => { const n = NPCS.find(x => x.id === nid); const d = RPG._dbg(); d.loadMap(n.map, 1, 1, 'down'); const D = RPG._dbg(); D.talk(D.npcs.find(x => x.id === nid)); await new Promise(r => setTimeout(r, 100)); return !!document.querySelector('#mgp'); }""", nid)
            if r: ok(False, f'{nid}: minigame menu shown before a new conversation'); continue
            await pg.evaluate(CLICK, "document.querySelector('#ra') && !RPG._dbg().talking")
        done = await pg.evaluate("() => Object.keys(ST.rpg.done)")
        ok(len(done) >= 7, f'conversations completed on a fresh save: {done}')
        ok(await pg.evaluate("() => RPG.total()") >= 63, 'all 63+ conversations still there')
        await br.close()
    print('\nERRORS:', ERR if ERR else 'none')

async def guarded():
    try: await main()
    except Exception as e:
        print('EXC', str(e)[:300])
        try:
            pg = GP[0]; await pg.screenshot(path=f'{SHOTS}/zz_fail.png'); print('PANEL', (await pg.evaluate("() => document.querySelector('#rp') && document.querySelector('#rp').innerHTML"))[:1500])
        except Exception as e2: print('no shot', e2)
GP = []
asyncio.run(guarded())
sys.exit(1 if ERR else 0)
