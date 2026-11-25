#!/usr/bin/env python3
"""Record-and-listen test (Rec): browsers without working speech recognition, like Vanadium on GrapheneOS.

usage:  python3 -u tools/test_rec.py /path/to/chispa

Runs headless Chrome with a fake microphone in three setups:
  nosr     - no SpeechRecognition at all: "Grabarme" from the start, the mic is never touched before a tap
  vanadium - SpeechRecognition exists but fails with not-allowed while the mic is allowed (what Vanadium does):
             first tap switches to Grabarme, remembers it (chispa.norec), next start skips the recogniser
  privacy  - the recording only lives in memory: deleted on the next exercise, on leaving, and when the app is hidden;
             the mic track is stopped right after recording; nothing lands in ST or localStorage
Also checks the speak, recall and town "dilo de memoria" flows still finish. Uses port 8799.
"""
import asyncio, os, subprocess, sys, time
from playwright.async_api import async_playwright

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
PORT = 8799; URL = f'http://127.0.0.1:{PORT}/'
HELPERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'play_helpers.js')
CHROME = os.environ.get('CHROME', '/usr/bin/google-chrome')

# instrument getUserMedia / object URLs so the test can see when the mic is open and what is kept
INSTR = r"""
window.__gum = 0; window.__live = 0; window.__urls = new Set();
const g0 = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async c => { const s = await g0(c); window.__gum++; window.__live++; s.getTracks().forEach(t => { const st = t.stop.bind(t); t.stop = () => { if (t.readyState === 'live') window.__live--; st(); }; }); return s; };
const cu = URL.createObjectURL.bind(URL), ru = URL.revokeObjectURL.bind(URL);
URL.createObjectURL = o => { const u = cu(o); if (o instanceof Blob && /webm|ogg|mp4/.test(o.type)) window.__urls.add(u); return u; };
URL.revokeObjectURL = u => { window.__urls.delete(u); ru(u); };
"""
NOSR = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition; Object.defineProperty(window, 'webkitSpeechRecognition', {value: undefined});"
VANADIUM = r"""
class FakeSR { constructor() { this.lang = ''; } start() { window.__srStarts = (window.__srStarts || 0) + 1; setTimeout(() => { this.onerror && this.onerror({error: 'not-allowed'}); this.onend && this.onend(); }, 30); } stop() {} abort() {} }
window.webkitSpeechRecognition = FakeSR; window.SpeechRecognition = FakeSR;
"""

COMMON = r"""
  const bad = [], info = []; const AP = window.AP;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ok = (c, m) => { if (!c) bad.push(m); };
  const k = Object.keys(ITEMS).find(x => x.startsWith('s|') && ITEMS[x].u === 1);
  const it = ITEMS[k];
  async function startLesson() { await AP.closeModals(); go('camino'); await sleep(50); document.querySelector('#go').click(); await sleep(80); const tip = document.querySelector('#tipgo'); if (tip) { tip.click(); await sleep(40); } if (document.querySelector('#sq')) { document.querySelector('#sq').click(); await sleep(40); } }
  function show(ex) { S.q.splice(S.i, 0, ex); renderEx(); }
  async function record(ms = 600) {
    const mb = document.querySelector('#mic'); ok(mb && /Grabarme/.test(mb.textContent), 'button should say Grabarme, says: ' + (mb && mb.textContent));
    mb.click(); await sleep(400); ok(window.__live === 1, 'mic should be open while recording, live=' + window.__live);
    ok(/Parar/.test(mb.textContent), 'button should say Parar while recording');
    await sleep(ms); mb.click(); await sleep(400);
    ok(window.__live === 0, 'mic must be closed right after recording, live=' + window.__live);
    ok(!!Rec.url && window.__urls.size === 1, 'one recording in memory');
    ok(!!document.querySelector('#heard .recplay'), 'Escúchate button shown');
  }
"""

def scenario(body):
    return "(async () => {" + COMMON + body + "\n  return {bad: bad.concat((AP.log || []).map(x => x.kind + ': ' + x.detail)), info};\n})()"

NOSR_JS = scenario(r"""
  ok(!Mic.d && Rec.ok && canMic(), 'no recogniser: Rec should be the mic');
  await startLesson(); ok(!!S, 'lesson started');
  ok(window.__gum === 0, 'mic must not be touched before a tap');
  // speak
  show({type: 'speak', es: it.es, en: it.en, k, keys: [k]}); await sleep(50);
  await record();
  document.querySelector('.recplay').click(); await sleep(100);
  const st = JSON.stringify(ST), ls = Object.keys(localStorage).join(',');
  ok(!/blob:|webm/.test(st) && !/blob:/.test(JSON.stringify(localStorage)), 'nothing about the recording in ST or localStorage');
  const i0 = S.i; document.querySelector('#said').click(); await sleep(700);
  ok(S && S.i === i0 + 1, 'Lo he dicho still finishes the speak exercise');
  ok(!Rec.url && window.__urls.size === 0, 'recording deleted on the next exercise');
  // recall: record, Mostrar keeps Escúchate to compare, answer, deleted
  show({type: 'recall', prompt: it.en, target: it.es, k, keys: [k]}); await sleep(50);
  await record();
  document.querySelector('#show').click(); await sleep(60);
  ok(!!document.querySelector('#heard .recplay') && !document.querySelector('#rv').hidden, 'after Mostrar: original + Escúchate to compare');
  document.querySelector('#r2').click(); await sleep(900);
  ok(!Rec.url && window.__urls.size === 0, 'recall recording deleted after answering');
  // recording, then Mostrar while still recording: stops the mic
  show({type: 'recall', prompt: it.en, target: it.es, k, keys: [k]}); await sleep(50);
  document.querySelector('#mic').click(); await sleep(400); document.querySelector('#show').click(); await sleep(400);
  ok(window.__live === 0, 'Mostrar stops a running recording');
  // app goes to background: deleted
  ok(!!Rec.url, 'recording there before hiding');
  Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'));
  ok(!Rec.url && window.__urls.size === 0, 'recording deleted when the app is hidden'); delete document.hidden;
  // leaving the lesson mid-recording
  show({type: 'speak', es: it.es, en: it.en, k, keys: [k]}); await sleep(50);
  document.querySelector('#mic').click(); await sleep(400); closeScreen(); await sleep(300);
  ok(window.__live === 0 && !Rec.url && window.__urls.size === 0, 'leaving the lesson closes the mic and deletes the recording');
  info.push(`speak, recall, background and leaving checked; mic opened ${window.__gum}x, only on taps`);
""")

VANADIUM_JS = scenario(r"""
  ok(!!Mic.d && Mic.kind === 'web', 'fake recogniser picked up at first');
  await startLesson();
  show({type: 'speak', es: it.es, en: it.en, k, keys: [k]}); await sleep(50);
  let mb = document.querySelector('#mic'); ok(/Grabar/.test(mb.textContent) && !/Grabarme/.test(mb.textContent), 'recognition button first');
  mb.click(); await sleep(400);
  ok(!Mic.d, 'recogniser switched off after not-allowed with the mic granted');
  ok(localStorage.getItem('chispa.norec') === '1', 'remembered for next time');
  ok(/Grabarme/.test(mb.textContent), 'same button now says Grabarme: ' + mb.textContent);
  ok(/Grabarme/.test(document.querySelector('#heard').textContent), 'explains what to do');
  await record();
  info.push('first tap fell back to Grabarme and remembered it');
""")

VANADIUM2_JS = scenario(r"""
  ok(localStorage.getItem('chispa.norec') === '1', 'flag still set after reload');
  ok(!Mic.d && (window.__srStarts || 0) === 0, 'recogniser skipped on the next start');
  await startLesson();
  show({type: 'speak', es: it.es, en: it.en, k, keys: [k]}); await sleep(50);
  await record();
  info.push('second start goes straight to Grabarme');
""")

async def run(pw, name, init, js, keep_ctx=None):
    b = await pw.chromium.launch(executable_path=CHROME, args=['--mute-audio', '--autoplay-policy=no-user-gesture-required', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
    ctx = await b.new_context(viewport={'width': 400, 'height': 860}, service_workers='block', permissions=['microphone'])
    await ctx.add_init_script(INSTR + init)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(f'page error: {e}'))
    t0 = time.time(); results = []
    for i, part in enumerate(js):
        if i == 0: await pg.goto(URL)
        else: await pg.reload()
        await pg.wait_for_timeout(800)
        await pg.add_script_tag(path=HELPERS)
        try: r = await asyncio.wait_for(pg.evaluate(part), 60)
        except Exception as e: r = {'bad': [f'crashed: {e}'], 'info': []}
        results.append(r)
    await b.close()
    bad = [x for r in results for x in r['bad']] + errs
    print(f"\n== {name} ({time.time() - t0:.0f}s): {'OK' if not bad else str(len(bad)) + ' problem(s)'}")
    for r in results:
        for i in r['info']: print('   ' + i)
    for x in bad[:40]: print('   ✗ ' + x)
    return not bad

async def main():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    try:
        async with async_playwright() as pw:
            ok = await run(pw, 'no speech recognition', NOSR, [NOSR_JS])
            ok &= await run(pw, 'Vanadium-like recogniser', VANADIUM, [VANADIUM_JS, VANADIUM2_JS])
    finally:
        srv.terminate()
    print('\nALL OK' if ok else '\nFAILED'); sys.exit(0 if ok else 1)

asyncio.run(main())
