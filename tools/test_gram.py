"""Headless test of the grammar cards: a full card, the map, Seguir, old saves and grammar in Repaso.
usage: python3 -u tools/test_gram.py /path/to/chispa [shots_dir]"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(sys.argv[1]); SHOTS = sys.argv[2] if len(sys.argv) > 2 else '/tmp/shots'
os.makedirs(SHOTS, exist_ok=True)
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors, n = [], [0]

def shot(page, name):
    n[0] += 1; page.screenshot(path=f'{SHOTS}/{n[0]:02d}_{name}.png')

def fresh(ctx, state=None):
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    page.on('console', lambda m: m.type == 'error' and 'Failed to load resource' not in m.text and errors.append(f'console: {m.text}'))
    page.goto('http://127.0.0.1:8765/index.html')
    page.evaluate("""s => { localStorage.clear(); if (s) localStorage.setItem('chispa.v2', JSON.stringify(s)); }""", state)
    page.reload(); page.wait_for_timeout(600)
    page.evaluate("() => { ST.welcomed = 1; ST.auto = false; ST.wv = false; Store.save(); document.querySelectorAll('.modal').forEach(m => m.remove()); }")
    return page

def opt(page, v):
    return page.locator('.opt').filter(has=page.locator('xpath=self::*')).and_(page.locator(f'.opt[data-v="{v}"]')).first

def click(page, sel, t=250):
    page.locator(sel).first.click(); page.wait_for_timeout(t)

def cont(page):
    page.locator('#lnext').click(); page.wait_for_timeout(250)

def play_card(page, tag):
    """plays whatever grammar step is on screen correctly; returns the step type"""
    t = page.evaluate('S && S.q[S.i] ? S.q[S.i].type : null')
    if t == 'gex': shot(page, tag + '_gex'); click(page, '#ck')
    elif t == 'gask':
        right = page.evaluate('gramOf(S.q[S.i].g).ask[1][0]')
        shot(page, tag + '_gask'); opt(page, right).click(); click(page, '#ck'); shot(page, tag + '_gask_ok'); cont(page)
    elif t == 'grule': shot(page, tag + '_grule'); click(page, '#ck')
    elif t == 'gsort':
        shot(page, tag + '_gsort')
        for _ in range(6):
            label = page.locator('#gcard b').inner_text()
            j = page.evaluate("l => S.q[S.i].p[3].find(it => it[0] === l)[1]", label)
            page.locator(f'.gbtn[data-j="{j}"]').click(); page.wait_for_timeout(800)
        shot(page, tag + '_gsort_done'); cont(page)
    elif t == 'ggap':
        ans = page.evaluate('S.q[S.i].ans'); shot(page, tag + '_ggap')
        page.locator(f'.opt[data-v="{ans}"]').click(); click(page, '#ck'); shot(page, tag + '_ggap_ok'); cont(page)
    elif t == 'gfix':
        ex = page.evaluate('({wi: S.q[S.i].wi, right: S.q[S.i].p[3]})'); shot(page, tag + '_gfix')
        page.locator(f'.gtok[data-i="{ex["wi"]}"]').click(); page.wait_for_timeout(200)
        label = ex['right'] or '— quitarla —'
        opt(page, label).click(); click(page, '#ck'); shot(page, tag + '_gfix_ok'); cont(page)
    elif t == 'speak': shot(page, tag + '_speak'); click(page, '#said', 600)
    else: click(page, '#ck') if page.locator('#ck').count() else None
    return t

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--autoplay-policy=no-user-gesture-required'])
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

    # 1. new learner: Entrenar card, map, sheet, a whole card
    page = fresh(ctx)
    click(page, '[data-tab="entrenar"]'); shot(page, 'entrenar')
    assert 'Gramática' in page.locator('#dogram').inner_text()
    click(page, '#dogram'); shot(page, 'map')
    assert page.locator('.gli:not(.locked)').count() == 1, 'only unit 1 open for a new learner'
    click(page, '[data-gram="g1"]'); shot(page, 'sheet_g1')
    click(page, '#gs-go')
    steps = []
    for _ in range(12):
        if page.locator('.end').count(): break
        steps.append(play_card(page, 'g1'))
    page.wait_for_timeout(400); shot(page, 'end_g1')
    print('g1 steps:', steps)
    assert steps == ['gex', 'gask', 'grule', 'gsort', 'ggap', 'ggap', 'gfix', 'speak'], steps
    assert page.evaluate("!!ST.gram.g1.d"), 'card marked done'
    assert page.evaluate("GKEYS.g1.every(k => ST.items[k])"), 'puzzles became review items'
    click(page, '#chestBtn', 1300); click(page, '#endgo', 600)
    for _ in range(4):  # badge / goal celebrations
        if page.locator('.modal [data-close]').count(): click(page, '.modal [data-close]', 400)
    after = page.evaluate("() => ({tab: TAB, badge: !!ST.badges.gram1, done: gramDone(), keys: keysEarned()})"); print('after card:', after)
    assert after['badge'] and after['done'] == 1
    assert page.evaluate('Number.isFinite(ST.xp) && ST.xp > 0'), 'xp is a number'

    # 2. every card plays through (all 30), in practice-free full mode
    page = fresh(ctx, None)
    page.evaluate("() => { ST.open = 30; Store.save(); }")
    for G in page.evaluate('GRAM.map(G => G.id)'):
        page.evaluate("id => startGram(id, {from: 'map'})", G)
        page.wait_for_timeout(150)
        for _ in range(12):
            if page.locator('.end').count(): break
            play_card(page, G) if G in ('g17', 'g25') else None
            if G not in ('g17', 'g25'):
                # quick path: answer through the session helpers without screenshots
                t = page.evaluate('S && S.q[S.i] ? S.q[S.i].type : null')
                if t in ('gex', 'grule'): click(page, '#ck', 60)
                elif t == 'gask': opt(page, page.evaluate('gramOf(S.q[S.i].g).ask[1][0]')).click(); click(page, '#ck', 60); cont(page)
                elif t == 'gsort':
                    for _ in range(6):
                        l = page.locator('#gcard b').inner_text(); j = page.evaluate("l => S.q[S.i].p[3].find(it => it[0] === l)[1]", l)
                        page.locator(f'.gbtn[data-j="{j}"]').click(); page.wait_for_timeout(720)
                    cont(page)
                elif t == 'ggap': page.locator(f'.opt[data-v="{page.evaluate("S.q[S.i].ans")}"]').click(); click(page, '#ck', 60); cont(page)
                elif t == 'gfix':
                    ex = page.evaluate('({wi: S.q[S.i].wi, right: S.q[S.i].p[3]})'); page.locator(f'.gtok[data-i="{ex["wi"]}"]').click()
                    opt(page, ex['right'] or '— quitarla —').click(); click(page, '#ck', 60); cont(page)
                elif t == 'speak': click(page, '#said', 500)
        assert page.locator('.end').count(), 'card did not finish: ' + G
        acc = page.locator('.end .t.acc b').inner_text(); xp = page.locator('.end .t.xp b').inner_text()
        assert xp.isdigit() and int(xp) > 50, f'{G} xp {xp}'
        assert acc == '100%', f'{G} accuracy {acc}'
        page.evaluate('closeScreen()')
    print('all 30 cards finish at 100%:', page.evaluate('gramDone()'))
    page.evaluate("() => { checkBadges(); Store.save(); go('progreso'); }"); page.wait_for_timeout(300)
    assert page.evaluate("!!ST.badges.gramall")

    # 3. an old save (no gram field), mid-way through unit 13
    old = {'v': 2, 'xp': 4200, 'gems': 300, 'streak': 4, 'best': 9, 'open': 13, 'prog': {str(u): 5 for u in range(1, 13)} | {'13': 1}, 'items': {}, 'badges': {}, 'welcomed': 1, 'bonus': {str(u): 1 for u in range(1, 13)}, 'rpg': {'map': 'casa', 'x': 5, 'y': 6, 'done': {}, 'flags': {}}}
    page = fresh(ctx, old)
    info = page.evaluate("() => ({gram: ST.gram, newCards: gramNew().length, seguir: nextStep().label})"); print('old save:', info)
    assert info['gram'] == {} and info['newCards'] == 13 and 'Wilma explica' in info['seguir']
    shot(page, 'camino_old_save')
    page.evaluate('nextStep().run()'); page.wait_for_timeout(300); shot(page, 'seguir_gex')
    assert page.locator('#gskip').count() == 1, 'Seguir shows Ahora no'
    click(page, '#gskip', 400)
    info = page.evaluate("() => ({skip: !!ST.gram.g13.s, seguir: nextStep().label, tab: TAB})"); print('after skip:', info)
    assert info['skip'] and 'Wilma explica' not in info['seguir']
    shot(page, 'camino_after_skip')

    # 4. Guía button opens the card; end-of-lesson offer
    page.evaluate('showTip(12)'); page.wait_for_timeout(200); shot(page, 'guia_g12')
    click(page, '#tipgram', 300); assert page.evaluate("S.kind === 'gram' && S.g === 'g12'")
    page.evaluate('closeScreen(); S = null')
    page.evaluate("() => { ST.gram = {}; ST.prog[13] = 1; Store.save(); startSession('lesson', {u: 13, node: 1, q: [exSpeak('Hola', 'Hello')]}); }"); page.wait_for_timeout(200)
    click(page, '#said', 700); click(page, '#chestBtn', 1300); shot(page, 'end_offer')
    assert page.locator('#endgram').is_visible()
    click(page, '#endgram', 600)
    for _ in range(30):
        if not page.locator('.modal [data-close]').count(): break
        click(page, '.modal [data-close]', 350)
    page.wait_for_timeout(300)
    assert page.evaluate("S && S.kind === 'gram' && S.g === 'g13'"), 'end-screen button starts the card'
    page.evaluate('closeScreen(); S = null')

    # 5. grammar puzzles show up in Repaso, every type renders
    page.evaluate("() => { ST.open = 30; GRAM.forEach(G => { ST.gram[G.id] = {d: 1}; GKEYS[G.id].forEach(k => ST.items[k] = [2, today() - 1, 1, 0, 0]); }); Store.save(); }")
    q = page.evaluate("genReview().map(e => e.type)"); print('review types:', q)
    assert any(t in ('gsort', 'ggap', 'gfix') for t in q)
    page.evaluate("startSession('review', {q: genGramReview()})"); page.wait_for_timeout(200)
    for _ in range(10):
        if page.locator('.end').count(): break
        play_card(page, 'rev')
    assert page.locator('.end').count()
    page.evaluate('closeScreen(); S = null')
    page.evaluate("openGramMap()"); page.wait_for_timeout(200); shot(page, 'map_all_done')
    page.evaluate("closeScreen(); go('progreso')"); page.wait_for_timeout(200)
    page.locator('.stat', has_text='grammar').scroll_into_view_if_needed(); shot(page, 'progreso_stat')

    # 6. notebook ignores grammar puzzles; wrong answers in a card
    page.evaluate('openNotebook()'); page.wait_for_timeout(200)
    assert page.evaluate("!$$('.nitem').some(b => b.dataset.k.startsWith('p|'))")
    page.evaluate("closeScreen(); startGram('g8', {from: 'map'})"); page.wait_for_timeout(150)
    click(page, '#ck')
    wrong = page.evaluate("gramOf('g8').ask[1][2]"); opt(page, wrong).click(); click(page, '#ck'); shot(page, 'gask_wrong'); cont(page)
    assert page.evaluate("S.q[S.i].type") == 'grule', 'a wrong noticing answer does not come back'
    click(page, '#ck')
    for _ in range(6):  # sort everything into box 0
        page.locator('.gbtn[data-j="0"]').click(); page.wait_for_timeout(1350)
    shot(page, 'gsort_wrong')
    assert page.locator('#ls.show.no').count(), 'many sort mistakes = not ok'
    cont(page)
    ans = page.evaluate('S.q[S.i].opts.find(o => o !== S.q[S.i].ans)')
    page.locator(f'.opt[data-v="{ans}"]').click(); click(page, '#ck'); shot(page, 'ggap_wrong')
    cont(page); cont_types = page.evaluate('S.q.map(e => e.type)')
    print('queue after mistakes:', cont_types)
    assert cont_types.count('ggap') == 3, 'a wrong gap comes back once'

    br.close()
srv.terminate()
print('\n'.join(errors) if errors else 'no page errors')
print('ALL GOOD' if not errors else 'ERRORS ABOVE')
