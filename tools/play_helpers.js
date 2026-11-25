// Helpers for tools/test_play.py: AP plays lessons through the real UI, TW walks the town and plays conversations.
// Auto-player for Chispa: plays sessions through the real UI and records anomalies.
window.AP = (() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const log = [];
  const issue = (kind, detail) => { log.push({kind, detail}); };
  const click = el => { if (!el) throw new Error('click on missing element'); el.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); el.click(); };
  async function waitFor(fn, ms = 4000, what = '') { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = fn(); if (v) return v; await sleep(25); } throw new Error('timeout waiting for ' + what); }
  async function closeModals(max = 10) { for (let i = 0; i < max; i++) { const m = document.querySelector('.modal'); if (!m) return; const b = m.querySelector('[data-close]') || m.querySelector('.btn'); if (b) click(b); else m.remove(); await sleep(60); } }

  function validate(ex) {
    const t = ex.type, where = `${S.kind} u${S.u} n${S.node} #${S.i} ${t}`;
    if (['pick', 'listen', 'lmean', 'gap', 'q', 'ggap'].includes(t)) {
      const n = ex.opts.map(o => norm(o));
      if (ex.opts.filter(o => o === ex.ans).length !== 1) issue('answer not exactly once in options', where + ' ' + JSON.stringify(ex.opts));
      if (new Set(n).size !== n.length) issue('duplicate options', where + ' ' + JSON.stringify(ex.opts));
      if (ex.opts.some(o => o === undefined || o === '')) issue('empty option', where);
      if (ex.opts.length < 3) issue('few options', where + ' ' + JSON.stringify(ex.opts));
      if (t === 'pick' || t === 'lmean' || t === 'listen') {
        // distractor meaning the same thing (both answers right)
        const k = ex.keys[0], it = ITEMS[k];
        ex.opts.filter(o => o !== ex.ans).forEach(o => { const other = Object.values(ITEMS).find(x => (x.es === o || x.en === o) && x.t === it.t && x !== it); if (other && (norm(other.en) === norm(it.en) || plain(other.es) === plain(it.es))) issue('distractor is also correct', where + ' ' + o); });
      }
    }
    if (t === 'build' || t === 'lbuild') {
      const tk = tokens(ex.target), pool = [...ex.tiles];
      for (const w of tk) { const i = pool.indexOf(w); if (i < 0) { issue('target token missing from tiles', where + ' ' + w); break; } pool.splice(i, 1); }
      const lower = ex.tiles.map(x => x.toLowerCase());
      // an extra tile identical to a target token makes two tiles interchangeable but harmless; flag extras that equal a target token
      pool.forEach(x => { if (tk.map(y => y.toLowerCase()).includes(x.toLowerCase())) issue('extra tile duplicates target word', where + ' ' + x + ' :: ' + ex.target); });
    }
    if (t === 'match') { const ens = ex.keys.map(k => norm(ITEMS[k].en)), ess = ex.keys.map(k => norm(ITEMS[k].es)); if (ex.keys.length < 3) issue('match with <3 pairs', where + ' ' + ex.keys.length); if (new Set(ess).size !== ess.length) issue('match duplicate Spanish', where); }
    if (['type', 'dict', 'recall', 'speak'].includes(t)) { const tg = ex.target || ex.es; if (!tg) issue('empty target', where); }
    if (ex.keys) ex.keys.forEach(k => { if (!ITEMS[k]) issue('unknown item key', where + ' ' + k); });
  }

  // answer the current exercise; mode: 'right' | 'wrong' | 'mixed'
  async function answerEx(mode) {
    const ex = S.q[S.i]; validate(ex);
    const wrong = mode === 'wrong' || (mode === 'mixed' && Math.random() < 0.25 && ex.type !== 'intro');
    const b = document.querySelector('#lb'), f = document.querySelector('#lf');
    switch (ex.type) {
      case 'intro': click(document.querySelector('#ck')); return;
      case 'pick': case 'listen': case 'lmean': case 'gap': case 'q': {
        const opts = [...b.querySelectorAll('.opt')];
        const o = wrong ? opts.find(x => x.dataset.v !== ex.ans) : opts.find(x => x.dataset.v === ex.ans);
        if (!o) { issue('no clickable option', ex.type); return; }
        click(o); await sleep(10); click(document.querySelector('#ck')); break;
      }
      case 'match': {
        const L = [...b.querySelectorAll('.pair[data-s="l"]')], R = [...b.querySelectorAll('.pair[data-s="r"]')];
        if (wrong && L.length > 1) { click(L[0]); click(R.find(r => norm(ITEMS[r.dataset.k].en) !== norm(ITEMS[L[0].dataset.k].en))); await sleep(20); }
        for (const l of L) { const r = R.find(x => !x.classList.contains('ok') && (x.dataset.k === l.dataset.k || norm(ITEMS[x.dataset.k].en) === norm(ITEMS[l.dataset.k].en))); click(l); click(r); await sleep(5); }
        await waitFor(() => document.querySelector('#ls.show') || S.q[S.i] !== ex, 3000, 'match end');
        break;
      }
      case 'build': case 'lbuild': {
        const tiles = [...b.querySelectorAll('#bank .tile')];
        const want = wrong ? [...tokens(ex.target)].reverse() : tokens(ex.target);
        for (const w of want) { const t = tiles.find(x => !x.classList.contains('used') && x.textContent === w); if (t) click(t); else issue('cannot place tile', w); }
        click(document.querySelector('#ck')); break;
      }
      case 'type': case 'dict': {
        const tb = document.querySelector('#tb'); tb.value = wrong ? 'xyz qwerty' : ex.target; tb.dispatchEvent(new Event('input', {bubbles: true}));
        click(document.querySelector('#ck')); break;
      }
      case 'recall': {
        click(document.querySelector('#show')); await sleep(10);
        click(document.querySelector(wrong ? '#r0' : '#r2')); break;
      }
      case 'speak': click(document.querySelector('#said')); break;
      // grammar cards (Gramática: Wilma explica)
      case 'gex': case 'grule': click(document.querySelector('#ck')); return;
      case 'gask': case 'ggap': {
        const right = ex.type === 'gask' ? gramOf(ex.g).ask[1][0] : ex.ans;
        const opts = [...b.querySelectorAll('.opt')];
        if (opts.filter(x => x.dataset.v === right).length !== 1) issue('grammar: correct option count', ex.type + ' ' + ex.g);
        const n = opts.map(x => norm(x.dataset.v)); if (new Set(n).size !== n.length) issue('grammar: duplicate options', ex.g + ' ' + JSON.stringify(n));
        click((wrong && ex.type === 'ggap') ? opts.find(x => x.dataset.v !== right) : opts.find(x => x.dataset.v === right)); await sleep(10); click(document.querySelector('#ck')); break;
      }
      case 'gsort': {
        const all = ex.p[3];
        for (let k = 0; k < all.length; k++) {
          const txt = document.querySelector('#gcard b').textContent, it = all.find(x => x[0] === txt);
          if (!it) { issue('grammar sort: unknown card', txt); break; }
          click(f.querySelector(`.gbtn[data-j="${wrong && k === 0 ? (it[1] + 1) % ex.p[2].length : it[1]}"]`));
          await waitFor(() => !document.querySelector('#gcard') || document.querySelector('#ls.show') || document.querySelector('#gcard b') && document.querySelector('#gcard b').textContent !== txt || k === all.length - 1 && document.querySelector('#ls.show'), 5000, 'sort card');
          if (document.querySelector('#ls.show')) break;
        }
        await waitFor(() => document.querySelector('#ls.show'), 5000, 'sort end');
        break;
      }
      case 'gfix': {
        click(b.querySelectorAll('.gtok')[ex.wi]); await sleep(20);
        const right = ex.p[3] || '— quitarla —', opts = [...b.querySelectorAll('#gfo .opt')];
        if (opts.filter(x => x.dataset.v === right).length !== 1) issue('grammar fix: correct option count', ex.g);
        click(wrong ? opts.find(x => x.dataset.v !== right) : opts.find(x => x.dataset.v === right)); await sleep(10); click(document.querySelector('#ck')); break;
      }
      default: issue('unknown exercise type', ex.type);
    }
    await sleep(20);
    const nx = document.querySelector('#ls.show #lnext'); if (nx) { click(nx); }
    else await sleep(470); // quick answers advance by themselves
  }

  async function finishEnd() {
    await waitFor(() => document.querySelector('.end'), 4000, 'end screen');
    const end = document.querySelector('.end'), txt = end.innerText;
    click(document.querySelector('#chestBtn'));
    await waitFor(() => document.querySelector('#endgo') && document.querySelector('#endgo').style.visibility === 'visible', 3000, 'chest');
    click(document.querySelector('#endgo')); await sleep(80); await closeModals();
    return txt;
  }

  // run the session currently on screen
  async function playSession(mode = 'right', maxSteps = 80) {
    let steps = 0;
    while (S && document.querySelector('#scr') && steps < maxSteps) {
      const i0 = S.i, q0 = S.q[S.i];
      try { await answerEx(mode); } catch (e) { issue('exception', String(e) + ' at ' + (q0 && q0.type)); return null; }
      steps++;
      if (S && S.i === i0 && S.q[S.i] === q0) { await sleep(500); if (S && S.i === i0 && S.q[S.i] === q0) { issue('stuck on exercise', q0.type); return null; } }
    }
    if (steps >= maxSteps) { issue('too many steps', S && S.kind); return null; }
    return finishEnd();
  }

  // press Seguir and play whatever it starts
  async function seguir(mode = 'right') {
    if (document.querySelector('#scr')) closeScreen();
    go('camino'); await closeModals();
    const label = document.querySelector('#go small').textContent;
    click(document.querySelector('#go')); await sleep(60);
    const tip = document.querySelector('#tipgo'); if (tip) { click(tip); await sleep(40); }
    // a scene opens a listening screen first
    if (document.querySelector('#sq')) { click(document.querySelector('#sq')); await sleep(40); }
    if (!S) { issue('Seguir started no session', label); return {label, end: null}; }
    const end = await playSession(mode);
    return {label, end};
  }
  return {log, issue, sleep, click, waitFor, closeModals, playSession, seguir, answerEx, validate, finishEnd};
})();
// Town helpers: walking by tapping tiles, and playing conversations through the panel.
window.TW = (() => {
  const {sleep, click, issue, waitFor} = AP;
  const D = () => RPG._dbg();
  function tapTile(tx, ty) {
    const d = D(), cv = document.querySelector('#rcv'), r = cv.getBoundingClientRect(), T = 16, VW = 10, VH = 9;
    const camX = Math.max(0, Math.min(d.M.w * T - VW * T, d.P.px + 8 - VW * T / 2)), camY = Math.max(0, Math.min(d.M.h * T - VH * T, d.P.py + 8 - VH * T / 2));
    const sx = tx * T + 8 - camX, sy = ty * T + 8 - camY;
    if (sx < 0 || sy < 0 || sx > VW * T || sy > VH * T) return false; // off screen
    cv.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, clientX: r.left + sx / (VW * T) * r.width, clientY: r.top + sy / (VH * T) * r.height}));
    return true;
  }
  // walk to a tile, tapping intermediate visible tiles along the BFS path if the goal is off screen
  async function walkTo(tx, ty, ms = 20000) {
    const t0 = Date.now(), map0 = D().M.id;
    while (Date.now() - t0 < ms) {
      const d = D(); if (d.M.id !== map0) return 'map:' + d.M.id; if (document.querySelector('.modal')) return 'modal';
      if (d.P.x === tx && d.P.y === ty && !d.P.mv) return 'ok';
      if (!d.P.mv) {
        if (!tapTile(tx, ty)) { const p = d.bfs(tx, ty); if (!p) return 'nopath'; let x = d.P.x, y = d.P.y; const DIR = {up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0]}; let last = null; for (const s of p) { x += DIR[s][0]; y += DIR[s][1]; const cx = x, cy = y; const cam = d; last = [cx, cy]; if (!tapTileVisible(cx, cy)) break; } }
        await sleep(200);
      } else await sleep(40);
    }
    return 'timeout';
  }
  function tapTileVisible(x, y) { return tapTile(x, y); }
  async function enterMapAt(map, x, y) { closeScreen(); ST.rpg.map = map; ST.rpg.x = x; ST.rpg.y = y; RPG.open(); await sleep(80); }

  // play the conversation in the panel until it ends
  async function playConv(convId) {
    const cv = CONVS[convId]; let guard = 0, wrongTried = false;
    while (D().talking && guard++ < 200) {
      const rz = document.querySelector('#rz');
      const rn = document.querySelector('#rn'), rs = document.querySelector('#rs'), rc = document.querySelector('#rc');
      if (rz && rz.querySelector('.opt[data-v]') && !rz.querySelector('.opt.right')) {
        const en = (document.querySelector('.rint b') || {}).textContent || '';
        const line = cv.l.find(l => l[0] === 'p' && '“' + l[2] + '”' === en);
        const opts = [...rz.querySelectorAll('.opt[data-v]')];
        if (!line) { issue('town: cannot identify line', convId + ' ' + en); click(opts[0]); }
        else {
          const right = opts.filter(o => o.dataset.v === line[1]);
          if (right.length !== 1) issue('town: correct option count ' + right.length, convId + ' ' + line[1]);
          const n = opts.map(o => norm(o.dataset.v)); if (new Set(n).size !== n.length) issue('town: duplicate options', convId + ' ' + JSON.stringify(n));
          if (opts.length < 3) issue('town: only ' + opts.length + ' options', convId);
          if (!wrongTried) { const w = opts.find(o => o.dataset.v !== line[1]); if (w) { click(w); wrongTried = true; await sleep(20); } }
          click(right[0] || opts[0]);
        }
        await sleep(30); continue;
      }
      if (rz && rz.querySelector('.opt[data-i]')) { click(rz.querySelector('.opt[data-i]')); await sleep(30); continue; }
      if (rc && rz && rz.querySelector('.bank')) {
        const en = (document.querySelector('.rint b') || {}).textContent || '';
        const line = cv.l.find(l => l[0] === 'p' && '“' + l[2] + '”' === en);
        const tiles = [...rz.querySelectorAll('.bank .tile')];
        if (!line) issue('town: cannot identify build line', convId);
        else for (const w of tokens(line[1])) { const t = tiles.find(x => !x.classList.contains('used') && x.textContent === w); if (t) click(t); else issue('town: tile missing', convId + ' ' + w); }
        click(rc); await sleep(30); continue;
      }
      if (rs) { click(rs); await sleep(20); const r2 = document.querySelector('#r2'); if (r2) click(r2); await sleep(30); continue; }
      if (document.querySelector('#r2')) { click(document.querySelector('#r2')); await sleep(30); continue; }
      if (rn) { click(rn); await sleep(30); continue; }
      await sleep(50);
    }
    if (guard >= 200) issue('town: conversation stuck', convId);
    await sleep(60); await AP.closeModals();
  }
  async function talkTo(npcId) {
    const n = NPCS.find(x => x.id === npcId), pc = D().pickConv(n);
    D().talk(n); await sleep(40);
    await playConv(pc.id);
    return pc.id;
  }
  return {D, tapTile, walkTo, enterMapAt, playConv, talkTo};
})();
