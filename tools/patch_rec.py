#!/usr/bin/env python3
"""Record-and-listen for browsers without speech recognition (Vanadium on GrapheneOS).
Applies string edits to index.html; each anchor must occur exactly once. Re-runnable on a fresh main."""
import sys, pathlib

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'index.html')
s = p.read_text(encoding='utf-8')
if 'const Rec = {' in s:
    print('already patched'); sys.exit(0)

def rep(old, new):
    global s
    n = s.count(old)
    if n != 1:
        sys.exit(f'anchor found {n}x: {old[:80]!r}')
    s = s.replace(old, new)

# 1. CSS for the "listen to yourself" button
rep(".heard{font-size:15px;color:var(--muted);min-height:22px;margin:8px 0}",
    ".heard{font-size:15px;color:var(--muted);min-height:22px;margin:8px 0}\n"
    ".recplay{display:inline-flex;align-items:center;gap:8px;padding:9px 16px;border-radius:14px;border:2px solid var(--line);background:transparent;color:var(--blue);font:inherit;font-weight:700;cursor:pointer}\n"
    ".recplay svg{width:18px;height:18px}\n"
    ".recnote{display:block;font-size:12px;color:var(--muted);margin-top:6px}")

# 2. Mic.init: skip the browser recogniser once we know it doesn't work on this device
rep("    const SRC = window.SpeechRecognition || window.webkitSpeechRecognition;\n    if (typeof STANDALONE",
    "    let SRC = window.SpeechRecognition || window.webkitSpeechRecognition;\n"
    "    try { if (localStorage.getItem(NOREC)) SRC = null; } catch (e) {} // recogniser failed here before (e.g. Vanadium): use Rec instead\n"
    "    if (typeof STANDALONE")

# 3. recogniser errors: switch to record-and-listen when there is no speech service
rep("""            if (er === 'not-allowed' || er === 'service-not-allowed') { M.d = null; CAP.dictation = null; toast('Microphone blocked. Allow it in the browser settings, or tap “Lo he dicho”.'); }
            else if (er === 'network') toast('Speech checking needs internet. Tap “Lo he dicho” instead.');
            else if (er === 'language-not-supported') { M.d = null; CAP.dictation = null; toast('Your phone can’t recognise Spanish yet. Tap “Lo he dicho”.'); }""",
"""            if (er === 'service-not-allowed' || er === 'language-not-supported' || (er === 'network' && navigator.onLine !== false)) M.noService();
            else if (er === 'not-allowed') {
              // Vanadium says not-allowed even when the mic is allowed: then it's the missing speech service, not the permission
              M.d = null; CAP.dictation = null;
              const blocked = () => toast('Microphone blocked. Allow it in the browser settings, or tap “Lo he dicho”.');
              try { navigator.permissions.query({name: 'microphone'}).then(p => p.state === 'granted' ? M.noService() : blocked(), blocked); } catch (e) { blocked(); }
            }
            else if (er === 'network') toast('Speech checking needs internet. Tap “Lo he dicho” instead.');""")

rep("  async stop() { try { await this.d.stop(); } catch (e) {} return this.buf; },",
    """  async stop() { try { await this.d.stop(); } catch (e) {} return this.buf; },
  // this browser has the speech API but nothing behind it (Vanadium/GrapheneOS has no Google speech service)
  noService() {
    this.d = null; CAP.dictation = null; try { localStorage.setItem(NOREC, '1'); } catch (e) {}
    toast(Rec.ok ? 'Speech checking doesn’t work in this browser. Tap “Grabarme” to hear yourself instead.' : 'Speech checking doesn’t work in this browser. Tap “Lo he dicho”.');
  },""")

# 4. the Rec module, after Mic
rep("\nconst Sfx = {\n",
"""
const NOREC = 'chispa.norec';
// Record and listen: say it, then hear yourself next to the course voice. For browsers without speech recognition (Vanadium on GrapheneOS).
// Privacy: the microphone only opens when you tap Grabarme and closes as soon as you stop. The recording only lives in memory
// for the current exercise; Rec.clear() deletes it (next exercise, leaving a screen, app in the background). Never saved, never sent.
const Rec = {
  ok: !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
  mr: null, stream: null, url: null, el: null, t: null, owner: null,
  get on() { return !!(this.mr && this.mr.state === 'recording'); },
  async start(owner, onDone) {
    this.clear(); this.owner = owner;
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}}); }
    catch (e) { if (this.owner === owner) this.owner = null; toast('No microphone access. You can allow it in the browser’s site settings, or just tap “Lo he dicho”.'); return false; }
    const off = () => stream.getTracks().forEach(t => t.stop());
    if (this.owner !== owner) { off(); return false; } // cleared while the permission prompt was open
    let mr; try { mr = new MediaRecorder(stream); } catch (e) { off(); this.owner = null; return false; }
    const chunks = [];
    mr.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
    mr.onstop = () => {
      off(); if (this.stream === stream) this.stream = null; if (this.mr === mr) this.mr = null;
      if (this.owner !== owner || !chunks.length) { chunks.length = 0; onDone && onDone(false); return; }
      this.url = URL.createObjectURL(new Blob(chunks, {type: mr.mimeType || 'audio/webm'})); chunks.length = 0; onDone && onDone(true);
    };
    this.stream = stream; this.mr = mr; mr.start();
    clearTimeout(this.t); this.t = setTimeout(() => this.stop(), 12000); // never leave the mic open
    return true;
  },
  stop() { clearTimeout(this.t); try { if (this.on) this.mr.stop(); } catch (e) {} },
  play() { if (!this.url) return; Voice.stop(); if (!this.el) this.el = new Audio(); this.el.src = this.url; this.el.play().catch(() => {}); },
  clear() {
    clearTimeout(this.t); this.owner = null;
    try { if (this.on) this.mr.stop(); } catch (e) {}
    if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
    this.mr = null;
    if (this.el) { try { this.el.pause(); this.el.removeAttribute('src'); this.el.load(); } catch (e) {} }
    if (this.url) { URL.revokeObjectURL(this.url); this.url = null; }
  }
};
document.addEventListener('visibilitychange', () => { if (document.hidden) Rec.clear(); });
const canMic = () => !!(Mic.d || Rec.ok);

const Sfx = {
""")

# 5. delete the recording whenever the exercise or screen changes
rep("function closeScreen() { Voice.stop(); ", "function closeScreen() { Voice.stop(); Rec.clear(); ")
rep("  const ex = S.q[S.i]; if (!ex) return endSession();\n", "  Rec.clear(); const ex = S.q[S.i]; if (!ex) return endSession();\n")
rep("function endSession() {\n  const s = S; S = null;", "function endSession() {\n  Rec.clear(); const s = S; S = null;")

# 6. recall exercise
rep("  f.innerHTML = Mic.d ? `<div class=\"row\"><button class=\"check ghost\" id=\"mic\" style=\"flex:1\">${icon('mic')} Grabar</button><button class=\"check\" id=\"show\"",
    "  f.innerHTML = canMic() ? `<div class=\"row\"><button class=\"check ghost\" id=\"mic\" style=\"flex:1\">${icon('mic')} Grabar</button><button class=\"check\" id=\"show\"")
rep("  if (Mic.d) { $('#rh').insertAdjacentHTML('afterend', '<div class=\"heard\" id=\"heard\"></div>'); $('#rh').textContent = 'Say it out loud. Tap Grabar and the phone checks you, or say it and tap Mostrar.';",
    "  if (canMic()) { $('#rh').insertAdjacentHTML('afterend', '<div class=\"heard\" id=\"heard\"></div>'); $('#rh').textContent = Mic.d ? 'Say it out loud. Tap Grabar and the phone checks you, or say it and tap Mostrar.' : 'Say it out loud. Tap Grabarme to hear yourself, then tap Mostrar to compare.';")

# 7. speak exercise
rep("  if (Mic.d) {\n    f.innerHTML = `<div class=\"row\"><button class=\"check ghost\" id=\"mic\"",
    "  if (canMic()) {\n    f.innerHTML = `<div class=\"row\"><button class=\"check ghost\" id=\"mic\"")

# 8. micCheck: recognition when available, otherwise record and listen
rep("""function micCheck(mb, heard, target, onHit, need = .6) {
  let rec = false; const label = () => { mb.innerHTML = `${icon('mic')} ${rec ? 'Escuchando…' : 'Grabar'}`; mb.classList.toggle('live', rec); };
  const judge = () => {
    if (!mb.isConnected) return;
    const s = Mic.score(target), txt = Mic.buf;""",
"""function micCheck(mb, heard, target, onHit, need = .6) {
  let rec = false; const own = {};
  const label = () => { const r = !Mic.d; mb.innerHTML = `${icon('mic')} ${rec ? (r ? 'Parar' : 'Escuchando…') : (r ? 'Grabarme' : 'Grabar')}`; mb.classList.toggle('live', rec); };
  label();
  const playBtn = () => {
    heard.innerHTML = `<button class="recplay" type="button">${icon('play')} Escúchate</button><span class="recnote">Only on this phone, deleted when you move on.</span>`;
    $('.recplay', heard).onclick = () => Rec.play();
  };
  const recTap = () => {
    if (rec) { Rec.stop(); return; }
    rec = true; label(); heard.textContent = 'Grabando… Tap Parar when you’re done.';
    Rec.start(own, got => { rec = false; if (mb.isConnected) label(); if (!heard.isConnected) return; if (got) { playBtn(); if (mb.isConnected) Rec.play(); } else heard.textContent = ''; })
      .then(started => { if (!started) { rec = false; if (mb.isConnected) { label(); heard.textContent = ''; } } });
  };
  const judge = () => {
    if (!mb.isConnected) return;
    if (!Mic.d) { label(); heard.textContent = Rec.ok ? 'Speech checking doesn’t work here. Tap Grabarme to record yourself and listen.' : ''; return; }
    const s = Mic.score(target), txt = Mic.buf;""")
rep("""  mb.onclick = () => {
    Voice.stop();
    if (!rec) { rec = true; label(); heard.textContent = 'Te escucho…';""",
"""  mb.onclick = () => {
    Voice.stop();
    if (!Mic.d) { if (Rec.ok) recTap(); return; }
    if (!rec) { rec = true; label(); heard.textContent = 'Te escucho…';""")

# 9. town review, "say it from memory" lines
rep("""<p class="rhint2">${icon('mic')} De memoria: dilo en voz alta.${Mic.d ? ' Tap Grabar and the phone checks you.' : ' Nobody is listening.'}</p><div class="heard" id="heard"></div>${Mic.d ? `""",
    """<p class="rhint2">${icon('mic')} De memoria: dilo en voz alta.${Mic.d ? ' Tap Grabar and the phone checks you.' : Rec.ok ? ' Tap Grabarme to hear yourself.' : ' Nobody is listening.'}</p><div class="heard" id="heard"></div>${canMic() ? `""")
rep("const heardOk = await new Promise(res => { $('#rs').onclick = () => res(false); if (Mic.d) micCheck(",
    "Rec.clear(); const heardOk = await new Promise(res => { $('#rs').onclick = () => { Rec.stop(); res(false); }; if (canMic()) micCheck(")
rep("""      $('#rz').innerHTML = `<button class="rline ok" id="rl">${icon('speaker')}<span>${esc(es)}</span></button><div class="row" style="margin-top:10px"><button class="check ghost" id="r0\"""",
    """      $('#rz').innerHTML = `<button class="rline ok" id="rl">${icon('speaker')}<span>${esc(es)}</span></button>${Rec.url ? `<div class="heard"><button class="recplay" type="button" id="rme">${icon('play')} Escúchate</button></div>` : ''}<div class="row" style="margin-top:10px"><button class="check ghost" id="r0\"""")
rep("""      $('#rl').onclick = () => Voice.speak(es); Voice.speak(es);
      const r = await new Promise(res => [0, 1, 2].forEach(i => $('#r' + i).onclick = () => res(i)));""",
    """      $('#rl').onclick = () => Voice.speak(es); Voice.speak(es); if ($('#rme')) $('#rme').onclick = () => Rec.play();
      const r = await new Promise(res => [0, 1, 2].forEach(i => $('#r' + i).onclick = () => res(i))); Rec.clear();""")

# 10. recall: Mostrar stops a running recording (the Escúchate button stays to compare)
rep("  $('#show').onclick = () => {\n    $('#rv').hidden = false;", "  $('#show').onclick = () => {\n    Rec.stop(); $('#rv').hidden = false;")

p.write_text(s, encoding='utf-8')
print('patched', p)
