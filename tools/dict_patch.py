#!/usr/bin/env python3
"""Patch Chispa's dictionary (dict.json) in place. Safe to run more than once.

What it does:
  1. Adds core words that the Wiktionary build dropped (no, a, vosotros, rosa, España, ...).
     New words are appended, so existing indices in D and F never change.
  2. Adds "F2": {form: [extra lemma indices]} for forms that belong to more than one word
     (fui -> ser AND ir, sé -> saber, trabajo -> trabajar, vamos -> ir, ...).
     Older app versions ignore F2, so the file stays compatible with them.
  3. Puts the everyday meaning first (de = "of", not "letter d"), and cleans template text
     ("smart inflection of dar", "[[Appendix:...]]", "<t:...>").

usage: python3 tools/dict_patch.py /path/to/chispa
"""
import collections, json, os, re, sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
PATH = os.path.join(ROOT, 'dict.json')
d = json.load(open(PATH, encoding='utf-8'))
D, F = d['D'], d['F']
F2 = d.setdefault('F2', {})

def index():
    idx = {}
    for i, e in enumerate(D):
        idx.setdefault(e[0], i)
    return idx

# ---------- 1. missing core words ----------
NEW = [
    ['no', [['adv', '', [['no'], ['not', 'before a verb: no sé = I don’t know']]], ['n', 'm', [['no (a refusal)']]]]],
    ['a', [['prep', '', [['to (direction): voy a Madrid'], ['at (time): a las ocho'], ['personal a: before a person who is the object: veo a Ana'], ['to, for (indirect object): se lo doy a Ana']]], ['n', 'f', [['letter: a']]]]],
    ['vosotros', [['pron', 'm-p', [['you (plural, informal; Spain)'], ['yourselves', 'after a preposition']]]]],
    ['vosotras', [['pron', 'f-p', [['you (plural, informal, all women; Spain)']]]]],
    ['bici', [['n', 'f', [['bike', 'short for bicicleta, colloquial']]]]],
    ['rosa', [['adj', '', [['pink']]], ['n', 'f', [['rose (flower)']]], ['n', 'm', [['pink (colour)']]]]],
    ['pizza', [['n', 'f', [['pizza']]]]],
    ['internet', [['n', 'm; f', [['the internet']]]]],
    ['teletrabajo', [['n', 'm', [['remote work, working from home']]]]],
    ['justificante', [['n', 'm', [['proof, receipt, certificate (a paper that proves something)']]]]],
    ['empadronarse', [['v', '', [['to register as a resident at the town hall (el padrón)']]]]],
    ['todes', [['pron', '', [['everyone, all of you', 'gender-neutral inclusive form of todos/todas']]]]],
    ['os', [['pron', '', [['you, to you (plural, informal; Spain) (form of vosotros)'], ['yourselves; each other', 'reflexive pronoun']]]]],
    ['España', [['prop', '', [['Spain']]]]],
    ['Alemania', [['prop', '', [['Germany']]]]],
    ['Francia', [['prop', '', [['France']]]]],
    ['Italia', [['prop', '', [['Italy']]]]],
    ['Inglaterra', [['prop', '', [['England']]]]],
    ['Europa', [['prop', '', [['Europe']]]]],
]
idx = index()
added = 0
for e in NEW:
    if e[0] not in idx:
        D.append(e); idx[e[0]] = len(D) - 1; added += 1

if 'os' in F and D[F['os']][0] == 'ox':  # junk link from the build ("os" is the Spain plural "you")
    del F['os']

def link(form, lemma):
    """form -> lemma, either as the main F link (if free) or as an extra F2 link."""
    if lemma not in idx or form == lemma:
        return False
    li = idx[lemma]
    if form in F:
        if F[form] == li: return False
        lst = F2.setdefault(form, [])
        if li in lst: return False
        lst.append(li); return True
    if form in idx:  # the form is also a headword (trabajo, nada, vamos): F2 keeps the headword first
        lst = F2.setdefault(form, [])
        if li in lst: return False
        lst.append(li); return True
    F[form] = li; return True

# ---------- 2a. hand-checked irregular forms ----------
HAND = {
    'ir': 'fui fuiste fue fuimos fuisteis fueron fuera fueras fuéramos fuerais fueran fuese fueses fuésemos fueseis fuesen vamos',
    'ser': 'era fuera',
    'saber': 'sé',
    'ver': 've ven',
    'venir': 'ven vino',
    'decir': 'di dicho',
    'dar': 'di',
    'comer': 'como',
    'salir': 'sal',
    'hacer': 'haz hecho',
    'poner': 'puesto',
    'sentar': 'siento sientes sienta sientan sentado',
    'reír': 'río',
    'nadar': 'nada',
    'estar': 'estado',
    'abrir': 'abierto',
    'escribir': 'escrito',
    'morir': 'muerto',
    'romper': 'roto',
    'volver': 'vuelto vuelta',
    'bueno': 'buena buenos buenas',
    'contar': 'cuenta',
}
# forms whose most common meaning should be listed first
PREFER = {'sé': 'saber'}
hand = 0
for lemma, forms in HAND.items():
    for f in forms.split():
        hand += link(f, lemma)
for f, lemma in PREFER.items():
    li = idx.get(lemma)
    if li is not None and f in F and F[f] != li:
        old = F[f]; F[f] = li
        F2[f] = [old] + [x for x in F2.get(f, []) if x not in (li, old)]

# ---------- 2b. verb forms that are also headwords (trabajo, pregunta, cuento, ...) ----------
# A headword H is linked to verb V when at least two "sibling" forms with the same stem are
# already known forms of V (trabajo: trabajas, trabaja, trabajan -> trabajar).
GROUPS = [
    ['o', 'as', 'a', 'an'], ['o', 'es', 'e', 'en'], ['e', 'es', 'en'], ['a', 'as', 'an'],
    ['é', 'aste', 'ó', 'amos', 'asteis', 'aron'], ['í', 'iste', 'ió', 'imos', 'isteis', 'ieron'],
    ['aba', 'abas', 'ábamos', 'aban'], ['ía', 'ías', 'íamos', 'ían'],
    ['ado', 'ada', 'ados', 'adas'], ['ido', 'ida', 'idos', 'idas'],
]
is_verb = lambda i: any(s[0] == 'v' for s in D[i][1])
auto = 0; auto_links = []
for H, hi in list(idx.items()):
    if ' ' in H or not H.islower() or len(H) < 3 or is_verb(hi):
        continue
    best = None
    for G in GROUPS:
        for e in G:
            if not H.endswith(e) or len(H) - len(e) < 2:
                continue
            X = H[:-len(e)]
            c = collections.Counter(F[X + e2] for e2 in G if e2 != e and X + e2 in F and is_verb(F[X + e2]))
            for li, n in c.items():
                if n >= 2 and D[li][0] != H and (best is None or n > best[1]):
                    best = (li, n)
    if best and link(H, D[best[0]][0]):
        auto += 1; auto_links.append((H, D[best[0]][0]))

# ---------- 3. meanings: everyday sense first, template text removed ----------
def clean(g):
    g = re.sub(r'\[\[\[Appendix:Glossary#[^|\]]*\|([^\]]*)\]\]', r'[\1', g)  # [[[Appendix:...|transitive]] -> [transitive
    g = re.sub(r'\s*\(#[^)]*…?\)?', '', g)                                    # (# long encyclopedic note
    g = re.sub(r'<t:([^>]*)>', r' (\1)', g)                                   # nave espacial<t:craft> -> nave espacial (craft)
    m = re.match(r'^smart inflection of ([^;]+?)(?:; (.*))?$', g)
    if m: g = f"{m.group(2)} (form of {m.group(1)})" if m.group(2) else f"form of {m.group(1)}"
    m = re.match(r'^inflection of ([^:;]+)[:;] (.*)$', g)
    if m: g = f"{m.group(2)} (form of {m.group(1).replace(',', ', ')})"
    m = re.match(r'^(.*?); inflection of (.*)$', g)
    if m: g = f"{m.group(1)} (form of {m.group(2)})"
    return re.sub(r'\s{2,}', ' ', g).strip()

fixed = 0
for e in D:
    for s in e[1]:
        for g in s[2]:
            c = clean(g[0])
            if c != g[0]: g[0] = c; fixed += 1

def letter_last(w):
    i = idx.get(w)
    if i is None: return
    ss = D[i][1]
    letters = [s for s in ss if s[0] == 'n' and re.match(r'(letter|name of the letter)', s[2][0][0], re.I)]
    if letters and ss[0] in letters:
        D[i][1] = [s for s in ss if s not in letters] + letters

for w in ['de', 'ese', 'o', 'e', 'u', 'te']:
    letter_last(w)

def first_pos(w, pos):
    i = idx.get(w)
    if i is None: return
    ss = D[i][1]; k = next((j for j, s in enumerate(ss) if s[0] == pos), None)
    if k: D[i][1] = [ss[k]] + ss[:k] + ss[k + 1:]

first_pos('vale', 'interj'); first_pos('mira', 'interj'); first_pos('oye', 'interj')
# Wiktionary headings that ended up as meanings
if 'venir' in idx:
    v = next(s for s in D[idx['venir']][1] if s[0] == 'v')
    if v[2][0][0].startswith('Senses relating'):
        v[2] = [['to come'], ['to arrive'], ['to come from, to be from [+de]'], ['to suit, to be convenient [+bien or mal]: me viene bien = it suits me']]
if 'ni' in idx:
    for s in D[idx['ni']][1]:
        if s[0] == 'conj' and s[2][0][0].startswith('Used when negating'): s[2][0][0] = 'nor, neither… nor (ni tú ni yo = neither you nor I)'
        if s[0] == 'adv' and s[2][0][0].startswith('Used in emphatic'): s[2][0][0] = 'not even (ni idea = no idea)'
if 'di' in idx:
    D[idx['di']][1].sort(key=lambda s: s[0] != 'v')
if 'muy' in idx:
    D[idx['muy']][1][0][2][0][0] = 'very (before adjectives and adverbs)'
# object pronouns: plain meanings instead of Wiktionary's "inflection of ..." notes
PRON = {
    'lo': [['him, it (direct object)'], ['you (formal, usted, a man)'], ['it, that (neuter): no lo sé = I don’t know (it)']],
    'la': [['her, it (direct object)'], ['you (formal, usted, a woman)'], ['it, this (in set phrases)', 'colloquial']],
}
for w, glosses in PRON.items():
    i = idx.get(w)
    if i is None: continue
    for s in D[i][1]:
        if s[0] == 'pron': s[2] = [list(g) for g in glosses]; break

# entries before "top" are ranked by how common they are; the ones after were added by hand
# for Chispa's course (all common), so the app must not treat them as rare words
if 'top' not in d and len(D) > 17122 and D[17122][0] == 'abuela':
    d['top'] = 17122
d['patch'] = 1
json.dump(d, open(PATH, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'added {added} words, {hand} hand links, {auto} automatic links, {fixed} glosses cleaned; '
      f'D={len(D)} F={len(F)} F2={len(F2)}')
if '-v' in sys.argv:
    for h, v in auto_links: print(f'  {h} -> {v}')
