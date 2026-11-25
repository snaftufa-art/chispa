#!/usr/bin/env python3
"""Run before every push. Stops one Claude session from overwriting what another one published.

usage: python3 tools/guard.py /path/to/chispa        (exit code 0 = safe to push)

Checks the working copy against the published version (origin/main, fetched fresh):
  1. you are on top of the published version (origin/main is an ancestor of HEAD), so git can't lose its commits
  2. every feature in tools/features.txt (published and local) is still in index.html
  3. no recorded line from the published AUDIO manifest disappeared (an old build would lose newer lines)
  4. no save field from the published DEF() disappeared (Rule #1: never remove save fields)
  5. every audio file in the manifest exists and is in sw.js FILES; VERSION changed if index.html changed
  6. the app's scripts parse
"""
import json, os, re, subprocess, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
git = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True)
bad, notes = [], []

f = git('fetch', '--depth=50', 'origin', 'main')
if f.returncode: bad.append('could not fetch origin/main: ' + f.stderr.strip()[-200:])
if git('merge-base', '--is-ancestor', 'origin/main', 'HEAD').returncode:
    bad.append('origin/main has commits you do not have. Run `git pull --rebase origin main`, re-apply your change on top of the new index.html, re-run the tests, then run this again.')

pub = git('show', 'origin/main:index.html').stdout
pub_sw = git('show', 'origin/main:sw.js').stdout
pub_feat = git('show', 'origin/main:tools/features.txt').stdout
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
sw = open(os.path.join(ROOT, 'sw.js'), encoding='utf-8').read()
loc_feat = open(os.path.join(ROOT, 'tools/features.txt'), encoding='utf-8').read() if os.path.exists(os.path.join(ROOT, 'tools/features.txt')) else ''

def feats(t): return [l.split(' | ')[0] for l in t.splitlines() if l.strip() and not l.startswith('#')]
for mk in dict.fromkeys(feats(pub_feat) + feats(loc_feat)):
    if mk not in html: bad.append(f'feature missing from index.html: "{mk}"')
for mk in feats(pub_feat):
    if mk not in feats(loc_feat): bad.append(f'feature line removed from tools/features.txt: "{mk}"')

aud = lambda t: json.loads(re.search(r'const AUDIO = (\{.*?\});\n', t).group(1))
A = aud(html)
if pub:
    gone = [k for k in aud(pub)['c'] if k not in A['c']]
    if gone: bad.append(f'{len(gone)} recorded lines from the published version are gone, e.g. {gone[:3]}')

def defkeys(t):
    m = re.search(r'const DEF = \(\) => (\(\{.*?\}\));\n', t, re.S)
    if not m: return None
    r = subprocess.run(['node', '-e', f'const today = () => 0, Date = {{now: () => 0}}; console.log(JSON.stringify(Object.keys({m.group(1)})))'], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None
dk_pub, dk = defkeys(pub), defkeys(html)
if dk_pub and dk: [bad.append(f'save field removed from DEF(): {k}') for k in dk_pub if k not in dk]
elif pub: notes.append('could not compare DEF() save fields')

fm = re.search(r'const FILES = (\[.*?\]);', sw); files = json.loads(fm.group(1)) if fm else []
for fn in A['f']:
    p = f'audio/{fn}.mp3'
    if not os.path.exists(os.path.join(ROOT, p)): bad.append(f'missing audio file {p}')
    if p not in files: bad.append(f'{p} is not in sw.js FILES (run tools/sw_update.py)')
for p in files:
    if p != './' and not os.path.exists(os.path.join(ROOT, p)): bad.append(f'sw.js lists a file that does not exist: {p}')
ver = lambda t: (re.search(r"const VERSION = '([0-9a-f]+)'", t) or [None, None])[1]
if pub and html != pub and ver(sw) == ver(pub_sw): bad.append('index.html changed but sw.js VERSION did not (run tools/sw_update.py)')

js = '\n'.join(re.findall(r'<script>([\s\S]*?)</script>', html))
r = subprocess.run(['node', '-e', 'new Function(require("fs").readFileSync(0, "utf8"))'], input=js, capture_output=True, text=True)
if r.returncode: bad.append('script does not parse: ' + r.stderr.strip().splitlines()[-1][:200])

for n in notes: print('note:', n)
if bad:
    print('NOT SAFE TO PUSH:'); [print(' -', b) for b in bad]; sys.exit(1)
print(f'safe to push: on top of origin/main, {len(feats(loc_feat))} features present, {len(A["c"])} recorded lines, {len(A["f"])} audio files')
