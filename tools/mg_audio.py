#!/usr/bin/env python3
"""Record the town minigame lines that have no audio and put them in audio/mg.<md5>.mp3 (rebuilt every run).
Other audio files and their manifest entries are left alone. Run tools/sw_update.py afterwards.

usage: python3 tools/mg_audio.py /path/to/chispa
needs: pip install "sherpa-onnx<1.13" soundfile numpy; ffmpeg; node; the Piper voices
  vits-piper-es_ES-sharvard-medium and vits-piper-es_ES-davefx-medium unpacked in $CHISPA_TTS (default /tmp/tts),
  from github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/<name>.tar.bz2
Voices as in the town: a = sharvard F, b = davefx, c = sharvard M, d = sharvard F lower, e = davefx higher, w = Wilma (sharvard F higher).
Sentences at speed 1.0 (like the town conversations), one- and two-word lines at 0.9.
"""
import hashlib, json, os, re, subprocess, sys, tempfile
import numpy as np, sherpa_onnx
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.'); TOOLS = os.path.dirname(os.path.abspath(__file__))
TTS = os.environ.get('CHISPA_TTS', '/tmp/tts'); SR = 22050
hp = os.path.join(ROOT, 'index.html'); html = open(hp, encoding='utf-8').read()
m = re.search(r'const AUDIO = (\{.*?\});\n', html); A = json.loads(m.group(1))
# drop the old minigame file (re-indexing the other files' clips)
keep = [i for i, f in enumerate(A['f']) if f.split('.')[0] != 'mg']; remap = {o: n for n, o in enumerate(keep)}
old = [f for f in A['f'] if f.split('.')[0] == 'mg']
A['f'] = [A['f'][i] for i in keep]; A['c'] = {k: [remap[v[0]], v[1], v[2]] for k, v in A['c'].items() if v[0] in remap}
tmp = tempfile.mktemp(suffix='.json')
subprocess.run(['node', os.path.join(TOOLS, 'mg_check.js'), hp, '--all', tmp], check=True, stdout=subprocess.DEVNULL)
need = [l for l in json.load(open(tmp)) if f'{l[0]}|{l[1]}' not in A['c']]
print(f'{len(need)} minigame lines to record')

def mk(d, name):
    return sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(
        model=f'{TTS}/{d}/{name}.onnx', tokens=f'{TTS}/{d}/tokens.txt', data_dir=f'{TTS}/{d}/espeak-ng-data'), num_threads=4)))
sh = mk('vits-piper-es_ES-sharvard-medium', 'es_ES-sharvard-medium'); dv = mk('vits-piper-es_ES-davefx-medium', 'es_ES-davefx-medium')
VOICES = {'a': (sh, 1, 1.0), 'b': (dv, 0, 1.0), 'c': (sh, 0, 1.0), 'd': (sh, 1, 0.92), 'e': (dv, 0, 1.14), 'w': (sh, 1, 1.22), 'g': (sh, 0, 0.84)}
def render(text, v):
    eng, sid, pitch = VOICES[v]; sp = 0.9 if len(text.split()) <= 2 else 1.0
    x = np.asarray(eng.generate(text, sid=sid, speed=sp / pitch).samples, dtype=np.float32)
    if pitch != 1.0: x = np.interp(np.linspace(0, len(x) - 1, int(len(x) / pitch)), np.arange(len(x)), x).astype(np.float32)
    idx = np.where(np.abs(x) > 0.012)[0]
    if len(idx): x = x[max(0, idx[0] - 900): idx[-1] + 2600]
    x = x * min(0.085 / (float(np.sqrt(np.mean(x ** 2))) or 1e-6), 0.97 / (float(np.abs(x).max()) or 1e-6))
    f = min(300, len(x) // 4)
    if f: x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f)
    return x

for f in old:
    p = os.path.join(ROOT, 'audio', f + '.mp3')
    if os.path.exists(p): os.remove(p)
if need:
    gap = np.zeros(int(SR * 0.45), np.float32); parts = [np.zeros(int(SR * 0.25), np.float32)]; pos = len(parts[0]); ent = []
    for v, t in need:
        x = render(t, v); ent.append((f'{v}|{t}', round(pos / SR, 3), round(len(x) / SR, 3))); parts += [x, gap]; pos += len(x) + len(gap)
    mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-codec:a', 'libmp3lame', '-b:a', '40k', '-ar', str(SR), '-ac', '1', '-f', 'mp3', '-'],
                         input=np.concatenate(parts).tobytes(), capture_output=True, check=True).stdout
    name = 'mg.' + hashlib.md5(mp3).hexdigest()[:8]; open(os.path.join(ROOT, 'audio', name + '.mp3'), 'wb').write(mp3)
    fi = len(A['f']); A['f'].append(name)
    for k, st, du in ent: A['c'][k] = [fi, st, du]
    print(f'  {name}.mp3: {len(ent)} clips, {pos / SR:.0f} s, {len(mp3) // 1024} KB')
html = html[:m.start(1)] + json.dumps(A, ensure_ascii=False, separators=(',', ':')) + html[m.end(1):]
open(hp, 'w', encoding='utf-8').write(html); print('manifest updated (now run tools/sw_update.py)')
