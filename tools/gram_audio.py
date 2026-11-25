#!/usr/bin/env python3
"""Record the grammar-card lines that have no audio yet and add them to Chispa's AUDIO manifest.

Voices match the rest of the app: Piper es_ES sharvard, speaker F (sid 1) for the course voice 'a';
Wilma ('w') is the same voice pitched up ~1.2x with the tempo kept. Clips are RMS-normalised to 0.08,
packed with 0.25 s lead-in and 0.45 s gaps, mono 22.05 kHz MP3 at 40 kb/s, hashed file names.

usage: python3 tools/gram_audio.py /path/to/chispa      (needs sherpa-onnx<1.13 and the model in /tmp/tts)
Rebuilds the ga1 / ga2 / gb1 files from scratch every run.
"""
import hashlib, json, os, re, subprocess, sys, tempfile
import numpy as np, sherpa_onnx

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
TOOLS = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get('CHISPA_TTS', '/tmp/tts/vits-piper-es_ES-sharvard-medium')
SR, LEAD, GAP, RMS = 22050, 0.25, 0.45, 0.08
GFILES = ('ga1', 'ga2', 'gb1')

html_path = os.path.join(ROOT, 'index.html')
html = open(html_path, encoding='utf-8').read()
m = re.search(r'const AUDIO = (\{.*?\});\n', html)
AUDIO = json.loads(m.group(1))

# 1. drop the old grammar files from the manifest (re-indexing the clips of the other files)
keep = [i for i, f in enumerate(AUDIO['f']) if f.split('.')[0] not in GFILES]
remap = {old: new for new, old in enumerate(keep)}
old_files = [f for f in AUDIO['f'] if f.split('.')[0] in GFILES]
AUDIO['f'] = [AUDIO['f'][i] for i in keep]
AUDIO['c'] = {k: [remap[v[0]], v[1], v[2]] for k, v in AUDIO['c'].items() if v[0] in remap}

# 2. which grammar lines still have no recording anywhere
tmp = tempfile.mktemp(suffix='.json')
subprocess.run(['node', os.path.join(TOOLS, 'gram_check.js'), html_path, html_path, '--all', tmp], check=True, stdout=subprocess.DEVNULL)
lines = json.load(open(tmp))
need = [l for l in lines if f'{l[0]}|{l[1]}' not in AUDIO['c']]
print(f'{len(lines)} grammar lines, {len(need)} to record')

cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(
    model=f'{MODEL}/es_ES-sharvard-medium.onnx', tokens=f'{MODEL}/tokens.txt', data_dir=f'{MODEL}/espeak-ng-data'), num_threads=4))
tts = sherpa_onnx.OfflineTts(cfg)

def ff(x, filt):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', filt, '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-'], input=x.astype(np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32)

def clip(voice, text):
    a = tts.generate(text, sid=1, speed=0.95)
    x = np.array(a.samples, dtype=np.float32)
    if voice == 'w': x = ff(x, f'asetrate={int(SR * 1.2)},aresample={SR},atempo={1 / 1.2:.5f}')
    nz = np.where(np.abs(x) > 0.01)[0]
    x = x[max(0, nz[0] - 200):nz[-1] + 200] if len(nz) else x
    x = x * (RMS / max(1e-6, np.sqrt(np.mean(x ** 2))))
    pk = np.abs(x).max()
    return x * (0.95 / pk) if pk > 0.95 else x

for f in old_files:
    p = os.path.join(ROOT, 'audio', f + '.mp3')
    if os.path.exists(p): os.remove(p)

for name in GFILES:
    group = [l for l in need if l[2] == name]
    if not group: continue
    parts, t, entries = [np.zeros(int(SR * LEAD), np.float32)], LEAD, []
    for voice, text, _ in group:
        x = clip(voice, text)
        entries.append((f'{voice}|{text}', round(t, 3), round(len(x) / SR, 3)))
        parts += [x, np.zeros(int(SR * GAP), np.float32)]; t += len(x) / SR + GAP
    wav = np.concatenate(parts)
    mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-codec:a', 'libmp3lame', '-b:a', '40k', '-ar', str(SR), '-ac', '1', '-f', 'mp3', '-'], input=wav.tobytes(), capture_output=True, check=True).stdout
    fname = f'{name}.{hashlib.md5(mp3).hexdigest()[:8]}'
    open(os.path.join(ROOT, 'audio', fname + '.mp3'), 'wb').write(mp3)
    fi = len(AUDIO['f']); AUDIO['f'].append(fname)
    for k, st, du in entries: AUDIO['c'][k] = [fi, st, du]
    print(f'  {fname}.mp3: {len(group)} clips, {t:.0f} s, {len(mp3) // 1024} KB')

html = html[:m.start(1)] + json.dumps(AUDIO, ensure_ascii=False, separators=(',', ':')) + html[m.end(1):]
open(html_path, 'w', encoding='utf-8').write(html)
print('manifest updated')
