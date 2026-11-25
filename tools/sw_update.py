#!/usr/bin/env python3
"""Make sw.js match index.html: FILES lists every audio file in the AUDIO manifest, VERSION changes with the content.
usage: python3 tools/sw_update.py /path/to/chispa"""
import hashlib, json, os, re, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read(); sw = open(os.path.join(ROOT, 'sw.js'), encoding='utf-8').read()
A = json.loads(re.search(r'const AUDIO = (\{.*?\});\n', html).group(1))
fm = re.search(r'const FILES = (\[.*?\]);', sw); files = json.loads(fm.group(1))
rest = [f for f in files if not f.startswith('audio/')]
audio = sorted('audio/' + f + '.mp3' for f in A['f'])
missing = [f for f in audio if not os.path.exists(os.path.join(ROOT, f))]
if missing: sys.exit(f'audio files in the manifest but not on disk: {missing}')
files = rest[:3] + audio + rest[3:]
ver = hashlib.md5((html + json.dumps(files)).encode()).hexdigest()[:10]
sw = sw[:fm.start(1)] + json.dumps(files) + sw[fm.end(1):]
sw = re.sub(r"const VERSION = '[0-9a-f]+';", f"const VERSION = '{ver}';", sw)
open(os.path.join(ROOT, 'sw.js'), 'w', encoding='utf-8').write(sw)
print(f'sw.js: {len(audio)} audio files, VERSION {ver}')
