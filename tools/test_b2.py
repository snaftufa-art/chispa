"""Headless test of B2 (units 31-40), the B2 gate (B1 done + 400 strong memories + Examen B1), Barrio Arcoiris,
Ligoteo (all five matches and stories) plus a walk through the whole town and every conversation.
usage: python3 -u tools/test_b2.py /path/to/chispa [shots_dir=/tmp/b2shots]   (needs playwright + /usr/bin/google-chrome)
"""
import os, sys
REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.'); SHOTS = sys.argv[2] if len(sys.argv) > 2 else '/tmp/b2shots'; os.makedirs(SHOTS, exist_ok=True)
import subprocess, atexit, time
_srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8799', '--bind', '127.0.0.1', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); atexit.register(_srv.terminate); time.sleep(1)  # own process: an in-process server is too slow for the chat timing
import asyncio, sys
from playwright.async_api import async_playwright
URL = 'http://127.0.0.1:8799/index.html'
SOLVE = r'''
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let guard = 0;
  while (S && guard++ < 80) {
    const ex = S.q[S.i]; if (!ex) break;
    const nextBtn = document.querySelector('#ls.show #lnext'); if (nextBtn) { nextBtn.click(); await sleep(30); continue; }
    const wrongOnce = ex.type === 'pick' && !S.tries.has(ex) && guard % 5 === 0;
    if (ex.type === 'intro') document.querySelector('#ck').click();
    else if (['pick','listen','gap','q','lmean'].includes(ex.type)) { const o = [...document.querySelectorAll('.opt')].find(b => wrongOnce ? b.dataset.v !== ex.ans : b.dataset.v === ex.ans); o.click(); document.querySelector('#ck').click(); }
    else if (ex.type === 'match') { for (const k of ex.keys) { const l = [...document.querySelectorAll('.pair[data-s=l]')].find(b => b.dataset.k === k && !b.classList.contains('ok')); const r = [...document.querySelectorAll('.pair[data-s=r]')].find(b => b.dataset.k === k && !b.classList.contains('ok')); l.click(); r.click(); } await sleep(320); }
    else if (ex.type === 'recall') { document.querySelector('#show').click(); await sleep(20); document.querySelector('#r2').click(); await sleep(460); }
    else if (ex.type === 'build' || ex.type === 'lbuild') { for (const t of tokens(ex.target)) { const b = [...document.querySelectorAll('#bank .tile:not(.used)')].find(x => x.textContent === t); if (!b) throw new Error('no tile ' + t + ' for ' + ex.target); b.click(); } document.querySelector('#ck').click(); }
    else if (ex.type === 'type' || ex.type === 'dict') { const tb = document.querySelector('#tb'); tb.value = ex.target.toLowerCase(); tb.oninput(); document.querySelector('#ck').click(); }
    else if (ex.type === 'speak') { document.querySelector('#said').click(); await sleep(460); }
    await sleep(30);
  }
  return {guard, ended: !!document.querySelector('.end')};
}'''
async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files'])
        pg = await b.new_page(viewport={'width': 390, 'height': 800})
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1600)
        await pg.screenshot(path=SHOTS + '/s1.png')
        await pg.evaluate("document.querySelector('.modal [data-close]')?.click()")
        # every generator for every unit must build without throwing and with sane options
        print(await pg.evaluate('''() => { let n = 0; const bad = [];
          for (const U of [...COURSE, ...EXTRA]) { const qs = [genLesson(U.id,0), genLesson(U.id,1), genLesson(U.id,2), genBoss(U.id)]; if (SCENES[U.id]) qs.push(genSceneQ(U.id));
            for (const q of qs) for (const ex of q) { n++; if (!ex) { bad.push(U.id + ' null'); continue; }
              if (ex.opts && (new Set(ex.opts).size !== ex.opts.length || ex.opts.length < 3)) bad.push(U.id + ' opts ' + JSON.stringify(ex.opts));
              if (ex.type === 'match' && ex.keys.length < 4) bad.push(U.id + ' match ' + ex.keys.length); } }
          for (let u = 1; u <= 19; u++) genTest(u);
          return {n, bad: bad.slice(0, 12), items: Object.keys(ITEMS).length}; }'''))
        # play lesson 1 fully
        await pg.evaluate("startNode(1,0)"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('#tipgo')?.click()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=SHOTS + '/s2.png')
        print(await pg.evaluate(SOLVE))
        await pg.wait_for_timeout(300); await pg.screenshot(path=SHOTS + '/s3.png')
        await pg.evaluate("document.querySelector('#chestBtn').click()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("document.querySelector('#endgo').click()"); await pg.wait_for_timeout(300)
        for _ in range(5):
            await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(120)
        # rest of unit 1 + boss + scene, a tema, review, rayo
        for call in ["startNode(1,1)", "startNode(1,2)", "openScene(1); document.querySelector('#sq').click()", "startNode(1,4)", "startNode(104,0); document.querySelector('#tipgo')?.click()", "startNode(103,3)", "startSession('review',{q:genReview()})", "startSession('test',{u:3,q:genTest(3)})"]:
            await pg.evaluate(call); await pg.wait_for_timeout(150)
            r = await pg.evaluate(SOLVE); print(call[:28], r)
            await pg.evaluate("document.querySelector('#chestBtn').click()"); await pg.wait_for_timeout(1150)
            await pg.evaluate("document.querySelector('#endgo').click()"); await pg.wait_for_timeout(150)
            for _ in range(6):
                await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        print(await pg.evaluate("({prog: ST.prog, open: ST.open, xp: ST.xp, streak: ST.streak, seen: seenKeys().length, badges: Object.keys(ST.badges), quests: ST.quests.d})"))
        await pg.screenshot(path=SHOTS + '/s4.png')
        for tab in ['entrenar', 'temas', 'progreso']:
            await pg.evaluate(f"go('{tab}')"); await pg.wait_for_timeout(150); await pg.screenshot(path=f'{SHOTS}/s_{tab}.png', full_page=False)
        await pg.evaluate("startRayo()"); await pg.wait_for_timeout(200)
        await pg.evaluate('''() => { for (let i = 0; i < 5; i++) { const l = document.querySelector('#rl .pair:not(.ok)'); const k = l.textContent; const key = Object.values(ITEMS).find(x => x.t === 'w' && x.es === k); const r = [...document.querySelectorAll('#rr .pair:not(.ok)')].find(b => b.textContent === key.en); l.click(); r && r.click(); } }''')
        await pg.wait_for_timeout(500); await pg.screenshot(path=SHOTS + '/s_rayo.png')
        await pg.evaluate("document.querySelector('#rx').click()"); await pg.wait_for_timeout(200)
        for _ in range(6):
            await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(100)
        print('typed checks', await pg.evaluate("[checkTyped('adios','adiós').ok, checkTyped('madre','la madre').ok, checkTyped('hola','adiós').ok, checkTyped('grasias','gracias').ok, checkTyped('me llamo tom','Me llamo Tom.').ok]"))

        # ---- the town ----
        await pg.evaluate("go('camino'); RPG.open()"); await pg.wait_for_timeout(700)
        await pg.screenshot(path=SHOTS + '/r1.png')
        TALK = """async (id) => { const sleep = ms => new Promise(r => setTimeout(r, ms)); const d = RPG._dbg(); const n = NPCS.find(x => x.id === id); d.talk(n); let guard = 0;
          while (guard++ < 120) { await sleep(25); const D = RPG._dbg(); if (!D.talking) break;
            const mgt = document.querySelector('#mgt') || document.querySelector('#mgx'); if (mgt) { mgt.click(); continue; }
            const nb = document.querySelector('#rn'); if (nb) { nb.click(); continue; }
            const rs = document.querySelector('#rs'); if (rs) { rs.click(); continue; }
            const r2 = document.querySelector('#r2'); if (r2) { r2.click(); continue; }
            const intent = document.querySelector('.rint b'); const en = intent ? intent.textContent.slice(1, -1) : null; const it = en && UNIT_KEYS[200].s.map(k => ITEMS[k]).find(x => x.en === en);
            const opts = [...document.querySelectorAll('#rz .opt:not(.right):not(.wrong)')];
            if (opts.length && it) { (opts.find(o => o.dataset.v === it.es) || opts[0]).click(); continue; }
            if (opts.length) { opts[0].click(); continue; }
            const rc = document.querySelector('#rc'); if (rc && it) { for (const t of tokens(it.es)) { const b = [...document.querySelectorAll('#rz .bank .tile:not(.used)')].find(x => x.textContent === t); b && b.click(); } rc.click(); continue; } }
          for (let i = 0; i < 6; i++) { document.querySelector('.modal [data-close]')?.click(); await sleep(60); }
          return {guard, done: ST.rpg.done, flags: ST.rpg.flags}; }"""
        print('wilma1', await pg.evaluate(TALK, 'wilma'))
        # walk out of the house by tapping the exit, then check we are on the street
        print('walk', await pg.evaluate("""async () => { const sleep = ms => new Promise(r => setTimeout(r, ms)); const d = RPG._dbg(); const p = d.bfs(4, 8); return {path: p}; }"""))
        box = await pg.locator('#rcv').bounding_box()
        await pg.mouse.click(box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.95); await pg.wait_for_timeout(1500)
        print('after exit', await pg.evaluate("({map: RPG._dbg().M.id, x: RPG._dbg().P.x, y: RPG._dbg().P.y})"))
        await pg.screenshot(path=SHOTS + '/r2.png')
        # every map loads, every NPC is reachable, every conversation runs three times (choose, build, recall)
        print('reach', await pg.evaluate("""() => { const bad = []; for (const n of NPCS) { const pl = PLACES[n.map]; const ch = pl.rows[n.y][n.x]; if (ch !== '.' && ch !== '=' && ch !== 'r' && ch !== 'd' && ch !== ',') bad.push(n.id + ' on ' + ch); } return bad; }"""))
        for nid in ['paqui', 'wilma', 'lucia', 'alex', 'noa', 'lucia', 'mar', 'mari', 'mar', 'dani', 'rosa', 'dani', 'churro', 'michi', 'lola', 'senora', 'turista', 'tormenta', 'sergio', 'juanjo', 'samir', 'iker', 'nico', 'wilma', 'wilma', 'alex', 'alex']:
            r = await pg.evaluate(TALK, nid)
            if r['guard'] >= 120: print('STUCK', nid)
        for nid in ['wilma', 'ines', 'wilma', 'nuria', 'manolo', 'nuria', 'kike', 'begona', 'marisa', 'yoli', 'pili', 'jacinto', 'amparo', 'ruben', 'noa_f', 'dani_p', 'ivan', 'toni', 'coco', 'sol', 'lucia_c']:
            r = await pg.evaluate(TALK, nid)
            if r['guard'] >= 120: print('STUCK', nid)
        # ride the train: stand on the platform in the station and walk up onto the rails
        await pg.evaluate("(() => { ST.rpg.map = 'estacion'; ST.rpg.x = 5; ST.rpg.y = 2; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=SHOTS + '/r_estacion.png')
        await pg.keyboard.down('ArrowUp'); await pg.wait_for_timeout(260); await pg.keyboard.up('ArrowUp'); await pg.wait_for_timeout(700)
        print('train ->', await pg.evaluate("RPG._dbg().M.id"))
        await pg.screenshot(path=SHOTS + '/r_playa.png')
        # walk back into the beach station (door at 4,4) -> back in town station
        print('path to anden', await pg.evaluate("RPG._dbg().bfs(4, 4) !== null"))
        await pg.evaluate("(() => { const d = RPG._dbg(); })()")
        for m in ['ferreteria', 'enchufe', 'vet', 'farmacia', 'peluqueria', 'chiringuito']:
            await pg.evaluate(f"(() => {{ ST.rpg.map = '{m}'; ST.rpg.x = 4; ST.rpg.y = 7; closeScreen(); RPG.open(); }})()"); await pg.wait_for_timeout(300); await pg.screenshot(path=f'{SHOTS}/r_{m}.png')
        await pg.evaluate("(() => { ST.rpg.map = 'calle'; ST.rpg.x = 12; ST.rpg.y = 18; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(300); await pg.screenshot(path=SHOTS + '/r_market.png')
        await pg.evaluate("(() => { ST.rpg.map = 'calle'; ST.rpg.x = 30; ST.rpg.y = 14; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(300); await pg.screenshot(path=SHOTS + '/r_east.png')
        # ---- keys and construction: the metro is locked until you spend keys ----
        await pg.evaluate("(() => { ST.keysSpent = 0; ST.built = {}; ST.rpg.map = 'calle'; ST.rpg.x = 36; ST.rpg.y = 21; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=SHOTS + '/k1.png')
        print('keys free', await pg.evaluate("keysFree()"), 'earned', await pg.evaluate("keysEarned()"))
        await pg.keyboard.down('ArrowUp'); await pg.wait_for_timeout(200); await pg.keyboard.up('ArrowUp'); await pg.wait_for_timeout(500)
        print('obras modal', await pg.evaluate("!!document.querySelector('.modal #obgo') || !!document.querySelector('.modal #oblearn')"))
        await pg.screenshot(path=SHOTS + '/k2.png')
        await pg.evaluate("ST.xp += 20000; for (let u = 1; u <= 20; u++) ST.prog[u] = Math.max(ST.prog[u] || 0, 5); ST.open = Math.max(ST.open, 21); document.querySelector('.modal [data-close]')?.click()")  # metro: 15 keys after unit 20; await pg.wait_for_timeout(200)
        await pg.evaluate("(() => { ST.rpg.map = 'calle'; ST.rpg.x = 36; ST.rpg.y = 21; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(300)
        await pg.keyboard.down('ArrowUp'); await pg.wait_for_timeout(200); await pg.keyboard.up('ArrowUp'); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('#obgo').click()"); await pg.wait_for_timeout(300)
        for _ in range(4): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        print('built', await pg.evaluate("[ST.built.metro ? 'metro' : 'no', keysFree()]"))
        await pg.keyboard.down('ArrowUp'); await pg.wait_for_timeout(200); await pg.keyboard.up('ArrowUp'); await pg.wait_for_timeout(600)
        print('metro ->', await pg.evaluate("RPG._dbg().M.id"))
        await pg.screenshot(path=SHOTS + '/k3.png')
        await pg.evaluate("['ayto','banco','inmo','biblio','salud','nave','piso'].forEach(id => ST.built[id] = 1)")
        for nid in ['raul', 'concha', 'vega', 'wilma_p', 'ortega', 'hugo', 'carla', 'remedios', 'ane', 'leo']:
            r = await pg.evaluate(TALK, nid)
            if r['guard'] >= 120: print('STUCK', nid)
        print('barrio done', await pg.evaluate("['raul','concha','vega','inaug','ortega','hugo','carla','remedios','ane','leo'].filter(k => ST.rpg.done[k]).length"))
        for m in ['piso', 'ayto', 'biblio']:
            await pg.evaluate(f"(() => {{ ST.rpg.map = '{m}'; ST.rpg.x = 4; ST.rpg.y = 7; closeScreen(); RPG.open(); }})()"); await pg.wait_for_timeout(300); await pg.screenshot(path=f'{SHOTS}/r_{m}.png')
        await pg.evaluate("closeScreen(); go('camino')")
        # ---- the B2 gate: blocked first ----
        await pg.evaluate("(() => { ST.rpg.map = 'barrio'; ST.rpg.x = 29; ST.rpg.y = 9; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(650); await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keyup', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(500)
        print('gate shown', await pg.evaluate("!!document.querySelector('.modal .gate')"), await pg.evaluate("JSON.stringify(gateState())"))
        await pg.screenshot(path=SHOTS + '/g1.png')
        await pg.evaluate("document.querySelector('.modal [data-close]')?.click(); closeScreen()")
        # meet the conditions: finish B1, strengthen 400 items, pass the exam
        await pg.evaluate("(() => { for (let u = 21; u <= 30; u++) ST.prog[u] = 5; ST.open = 31; const n = today(); Object.keys(ITEMS).slice(0, 450).forEach(k => ST.items[k] = [5, n + 10, 3, 0, 0]); })()")
        await pg.evaluate("startSession('exam', {q: genExamB1()})"); await pg.wait_for_timeout(150)
        print('exam', await pg.evaluate(SOLVE), await pg.evaluate("document.querySelector('.end h2')?.textContent"))
        await pg.evaluate("document.querySelector('#chestBtn')?.click()"); await pg.wait_for_timeout(1150); await pg.evaluate("document.querySelector('#endgo')?.click()")
        for _ in range(8): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        print('gate after', await pg.evaluate("JSON.stringify(gateState())"))
        await pg.evaluate("(() => { ST.rpg.map = 'barrio'; ST.rpg.x = 29; ST.rpg.y = 9; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(650); await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keyup', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('#obgo')?.click()"); await pg.wait_for_timeout(300)
        for _ in range(12): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(150)
        await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(350); await pg.evaluate("document.dispatchEvent(new KeyboardEvent('keyup', {key: 'ArrowUp'}))"); await pg.wait_for_timeout(700)
        print('line 2 ->', await pg.evaluate("RPG._dbg().M.id"))
        await pg.screenshot(path=SHOTS + '/g2.png')
        # ---- Ligoteo: profile, five matches, chats and dates ----
        await pg.evaluate("closeScreen(); ST.auto = false; openLigoteo()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=SHOTS + '/l0.png')
        await pg.evaluate("document.querySelector('[data-k=pron][data-v=ella]').click()"); await pg.wait_for_timeout(100)
        await pg.evaluate("document.querySelector('#lgsave').click()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=SHOTS + '/l1.png')
        CHAT = '''async (id) => { const sleep = ms => new Promise(r => setTimeout(r, ms)); const M = MATCHES.find(m => m.id === id);
          let g = 0; while (g++ < 3000) { await sleep(60);
            if (document.querySelector('#lgdone') || document.querySelector('#lggo')) return 'end';
            const opts = [...document.querySelectorAll('#lgpanel .opt:not(.wrong):not(.right)')]; if (!opts.length) continue;
            if (document.querySelector('.lgq')) { const st = M.chats.flatMap(c => c.l).filter(s => s[0] === 'voice').find(s => opts.some(o => o.dataset.v === s[3][2])); const b = opts.find(o => st && o.dataset.v === st[3][2]); (b || opts[0]).click(); continue; }
            const step = M.chats.flatMap(c => c.l).find(s => s[0] === 'you' && opts.some(o => o.textContent === s[1][0][0] || s[1].some(x => x[0] === o.textContent)));
            const good = step && step[1].find(x => x[2]); const b = opts.find(o => good && o.textContent === good[0]); (g % 5 === 0 ? opts[0] : (b || opts[0])).click(); }
          return 'timeout · ' + JSON.stringify({modal: document.querySelector('.modal')?.innerText.slice(0, 120), screen: document.querySelector('.screen')?.className, tail: (document.querySelector('#lgpanel') || document.body).innerText.slice(-240)}); }'''
        for M in ['ainhoa', 'teo', 'sam', 'marcos', 'luz']:
            await pg.evaluate(f"openLigoteo('profile', '{M}')"); await pg.wait_for_timeout(200)
            if M == 'ainhoa': await pg.screenshot(path=SHOTS + '/l2.png')
            await pg.evaluate(f"(() => {{ const q = MATCHES.find(m => m.id === '{M}').bioq; [...document.querySelectorAll('#lgstep .opt')].find(b => b.dataset.v === q[2]).click(); }})()"); await pg.wait_for_timeout(700)
            await pg.evaluate(f"(() => {{ const M = MATCHES.find(m => m.id === '{M}'); const bs = [...document.querySelectorAll('#lgstep .opt')]; bs.find(b => !M.ice[+b.dataset.i][2]).click(); bs.find(b => M.ice[+b.dataset.i][2]).click(); }})()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.querySelector('#mgo')?.click()"); await pg.wait_for_timeout(150)
            for _ in range(4): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(60)
            r1 = await pg.evaluate(CHAT, M)
            if M == 'ainhoa': await pg.screenshot(path=SHOTS + '/l3.png')
            for _ in range(4): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(60)
            npc = {'ainhoa': 'ainhoa_c', 'teo': 'teo_r', 'sam': 'sam_b', 'marcos': 'marcos_m', 'luz': 'luz_l'}[M]
            await pg.evaluate("closeScreen(); RPG.open('arcoiris')"); await pg.wait_for_timeout(200)
            if M in ['teo', 'sam', 'luz']: await pg.evaluate(f"ST.built[{ {'teo':'\'roco\'','sam':'\'sirena\'','luz':'\'libreria\''}[M] }] = 1")
            rr = await pg.evaluate(TALK, npc)
            await pg.evaluate(f"closeScreen(); openLigoteo('chat', '{M}')"); await pg.wait_for_timeout(200)
            r2 = await pg.evaluate(CHAT, M)
            if M == 'luz': await pg.screenshot(path=SHOTS + '/l4.png')
            for _ in range(5): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(60)
            print('match', M, r1, rr['guard'], r2)
        print('lig', await pg.evaluate("JSON.stringify({done: Object.keys(ST.lig.done), keys: keysEarned(), badges: Object.keys(ST.badges).filter(b => ['b2','examen','arcoiris','match1','historias'].includes(b)), u400: UNIT_KEYS[400].s.filter(k => ST.items[k]).length})"))
        await pg.evaluate("closeScreen(); openLigoteo()"); await pg.wait_for_timeout(300); await pg.screenshot(path=SHOTS + '/l5.png')
        for nid in ['mateo', 'vero', 'rafa']:
            await pg.evaluate("closeScreen(); ST.built.centro = 1; RPG.open('arcoiris')"); await pg.wait_for_timeout(150)
            r = await pg.evaluate(TALK, nid); print('arco', nid, r['guard'])
        await pg.evaluate("(() => { ST.rpg.map = 'arcoiris'; ST.rpg.x = 15; ST.rpg.y = 13; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(400); await pg.screenshot(path=SHOTS + '/g3.png')
        for m in ['pluma', 'sirena', 'libreria']:
            await pg.evaluate(f"(() => {{ ST.rpg.map = '{m}'; ST.rpg.x = 4; ST.rpg.y = 7; closeScreen(); RPG.open(); }})()"); await pg.wait_for_timeout(250); await pg.screenshot(path=f'{SHOTS}/r_{m}.png')
        await pg.evaluate("closeScreen(); go('camino')")
        # B2 lessons
        for call in ["startNode(31,0)", "startNode(37,2)", "openScene(38); document.querySelector('#sq').click()", "startNode(40,4)"]:
            await pg.evaluate(call); await pg.wait_for_timeout(150); await pg.evaluate("document.querySelector('#tipgo')?.click()"); await pg.wait_for_timeout(100)
            r = await pg.evaluate(SOLVE); print('B2', call[:24], r)
            await pg.evaluate("document.querySelector('#chestBtn')?.click()"); await pg.wait_for_timeout(1150); await pg.evaluate("document.querySelector('#endgo')?.click()"); await pg.wait_for_timeout(150)
            for _ in range(6): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        # ---- B1 lessons ----
        for call in ["startNode(25,0)", "startNode(28,1)", "startNode(30,4)", "openScene(23); document.querySelector('#sq').click()", "startSession('bonus', {u: 21, q: genBonus(21)})"]:
            await pg.evaluate(call); await pg.wait_for_timeout(150); await pg.evaluate("document.querySelector('#tipgo')?.click()"); await pg.wait_for_timeout(100)
            r = await pg.evaluate(SOLVE); print('B1', call[:24], r)
            await pg.evaluate("document.querySelector('#chestBtn')?.click()"); await pg.wait_for_timeout(1150); await pg.evaluate("document.querySelector('#endgo')?.click()"); await pg.wait_for_timeout(150)
            for _ in range(6): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        await pg.evaluate("go('camino')"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('#u21')?.scrollIntoView()"); await pg.wait_for_timeout(200); await pg.screenshot(path=SHOTS + '/b1.png')
        await pg.evaluate("closeScreen(); go('camino')")
        # bonus lesson, notebook, wardrobe
        await pg.evaluate("startSession('bonus', {u: 1, q: genBonus(1)})"); await pg.wait_for_timeout(150)
        print('bonus', await pg.evaluate(SOLVE))
        await pg.evaluate("document.querySelector('#chestBtn').click()"); await pg.wait_for_timeout(1200); await pg.evaluate("document.querySelector('#endgo').click()")
        for _ in range(8): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(80)
        print('bonus saved', await pg.evaluate("ST.bonus"), 'next step', await pg.evaluate("nextStep().label"))
        await pg.evaluate("openNotebook()"); await pg.wait_for_timeout(200); await pg.screenshot(path=SHOTS + '/n1.png')
        await pg.fill('#nq', 'gracias'); await pg.wait_for_timeout(150); print('notebook search', await pg.evaluate("document.querySelectorAll('.nitem').length"))
        await pg.evaluate("closeScreen(); ST.gems = 500; go('progreso')")
        for w in ['gafas', 'panuelo', 'corona']:
            await pg.evaluate(f"wardTap('{w}')"); await pg.wait_for_timeout(150)
            for _ in range(4): await pg.evaluate("document.querySelector('.modal [data-close]')?.click()"); await pg.wait_for_timeout(60)
        print('wardrobe', await pg.evaluate("[ST.gems, ST.wear, Object.keys(ST.owned)]"))
        await pg.evaluate("document.querySelector('.wardrobe').scrollIntoView()"); await pg.wait_for_timeout(200); await pg.screenshot(path=SHOTS + '/w1.png')
        r = await pg.evaluate("({done: Object.keys(ST.rpg.done).length, total: RPG.total(), counts: ST.rpg.done, badges: Object.keys(ST.badges), items200: UNIT_KEYS[200].s.filter(k => ST.items[k]).length})"); print('town', r)
        for m in ['bar', 'super', 'colmena', 'kebab', 'taller', 'casa']:
            await pg.evaluate(f"(() => {{ ST.rpg.map = '{m}'; ST.rpg.x = 4; ST.rpg.y = 7; closeScreen(); RPG.open(); }})()"); await pg.wait_for_timeout(350); await pg.screenshot(path=f'{SHOTS}/r_{m}.png')
        await pg.evaluate("(() => { ST.rpg.map = 'calle'; ST.rpg.x = 12; ST.rpg.y = 11; closeScreen(); RPG.open(); })()"); await pg.wait_for_timeout(350); await pg.screenshot(path=SHOTS + '/r_plaza.png')
        print('audio', await pg.evaluate("""async () => { const t0 = Date.now(); await Voice.speak('hola'); const a = Date.now() - t0; const t1 = Date.now(); await Voice.speak('¡Miau! Soy Wilma. ¿Empezamos?', {v: 'w'}); return {hola_ms: a, wilma_ms: Date.now() - t1, unlocked: Voice.unlocked, clip: Voice.clip('hola'), files: AUDIO.f.length, clips: Object.keys(AUDIO.c).length}; }"""))
        await pg.evaluate("closeScreen()")
        await b.close()
    print('ERRORS', errs)
asyncio.run(main())
