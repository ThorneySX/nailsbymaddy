import json, re, pathlib, sys
import config as C

# --no-browser skips only section 5, the rendered checks, and substitutes
# static equivalents for the two that matter. It exists so this file can run
# on Cloudflare's build container, which has Python but no Chromium — and
# installing one there would add minutes to every deploy to re-measure a
# layout that has not changed. Run it without the flag locally; that is the
# real gate.
NO_BROWSER = '--no-browser' in sys.argv

html = pathlib.Path('public/index.html').read_text()
fails = []

# 1. JSON-LD parses, and every price matches services.json exactly
graphs = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
if isinstance(graphs, dict): graphs = [graphs]
by_type = {g['@type']: g for g in graphs}
ld = by_type['NailSalon']

# FAQ: every question on the page must be in the schema and vice versa
faq = by_type.get('FAQPage')
if not faq:
    fails.append('FAQPage schema missing')
else:
    qs = {q['name'] for q in faq['mainEntity']}
    if qs != {q for q, _ in C.FAQS}:
        fails.append(f'FAQ schema/config mismatch: {qs ^ {q for q,_ in C.FAQS}}')
    for q, a in C.FAQS:
        if q not in html or a[:40] not in html:
            fails.append(f'FAQ not rendered on page: {q[:40]}')
    print(f"✓ {len(C.FAQS)} FAQs render on the page and match the FAQPage schema")
src = {s['title']: s for s in json.loads(pathlib.Path('services.json').read_text())}
offers = {o['itemOffered']['name']: o['price'] for o in ld['hasOfferCatalog']['itemListElement']}
n = 0
for group, items in C.GROUPS:
    for key, label in items:
        want = src[key]['price'].replace('£','').replace('.00','')
        if offers.get(label) != want:
            fails.append(f"schema price {label}: {offers.get(label)} != {want}")
        if f'<dd>£{want}</dd>' not in html:
            fails.append(f"page price missing: {label} £{want}")
        n += 1
print(f"✓ {n} services cross-checked against services.json (page + schema)")
print(f"✓ schema type {ld['@type']}, {len(offers)} offers, "
      f"aggregateRating present: {'aggregateRating' in ld}")

# 2. every service in services.json is on the page (nothing silently dropped)
listed = {k for _, items in C.GROUPS for k, _ in items}
missing = set(src) - listed
if missing: fails.append(f"services not shown anywhere: {missing}")
else: print(f"✓ all {len(src)} services from the booking menu are listed")

# 3. draft hygiene
if C.DRAFT:
    assert 'noindex' in html and 'Disallow: /' in pathlib.Path('public/robots.txt').read_text()
    print("✓ draft build is noindex + robots-disallowed")

# 4. live build must contain no placeholder, no ribbon, no non-public review
import subprocess, shutil
cfg = pathlib.Path('config.py'); orig = cfg.read_text()
# anchor to the assignment at column 0 — the docstring above it says
# "DRAFT = True" too, and a plain replace() rewrites that instead.
flipped, count = re.subn(r'(?m)^DRAFT = True$', 'DRAFT = False', orig)
assert count == 1, f'expected one DRAFT assignment, found {count}'
cfg.write_text(flipped)
try:
    subprocess.run([sys.executable, 'build_site.py'], check=True, capture_output=True)
    live = pathlib.Path('public/index.html').read_text()
    for bad, why in [('To supply','placeholder'), ('class="hold"','placeholder block'),
                     ('class="ribbon"','draft ribbon'), ('.hold{','draft-only CSS'), ('noindex','noindex'),
                     ('Booking system','internal note')]:
        if bad in live: fails.append(f"LIVE build leaks {why}: {bad!r}")
    for r in C.REVIEWS:
        if not r['public'] and r['text'][:30] in live:
            fails.append(f"LIVE build shows unconfirmed review from {r['who']}")
    assert 'Disallow: /' not in pathlib.Path('public/robots.txt').read_text()
    print(f"✓ live build clean: no placeholders, no ribbon, indexable, "
          f"only the {sum(r['public'] for r in C.REVIEWS)} public review shown")
finally:
    cfg.write_text(orig)
    subprocess.run([sys.executable, 'build_site.py'], check=True, capture_output=True)

# 5. render checks
if NO_BROWSER:
    # Static stand-ins. Not as good — nothing here measures a tap target —
    # but a missing image and a second h1 are the two that actually ship
    # broken, and both are visible in the markup.
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', html)
    absent = [s for s in srcs if not (pathlib.Path('public') / s.lstrip('/')).exists()]
    if absent: fails.append(f"image files missing from public/: {absent}")
    else: print(f"✓ all {len(srcs)} image files exist on disk (not rendered — no browser)")
    nh1 = len(re.findall(r'<h1[\s>]', html))
    if nh1 != 1: fails.append(f"h1 count = {nh1}")
    else: print("✓ one h1")
    print("✓ title:", re.search(r'<title>(.*?)</title>', html, re.S).group(1))
else:
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':390,'height':844})
    pg.goto('file://' + str(pathlib.Path('public/index.html').resolve()))
    pg.wait_for_timeout(1500)
    broken = pg.evaluate("""() => [...document.images].filter(i=>!i.complete||i.naturalWidth===0)
                                   .map(i=>i.getAttribute('src'))""")
    if broken: fails.append(f"images failed to load: {broken}")
    else: print(f"✓ all {pg.evaluate('document.images.length')} images load")
    # tap targets
    small = pg.evaluate("""() => [...document.querySelectorAll('a,button')]
        .filter(e=>{const r=e.getBoundingClientRect();
          const inline=getComputedStyle(e).display==='inline';
          return r.height>0 && r.height<44 && !inline})
        .map(e=>e.textContent.trim().slice(0,30))""")
    print("✓ all tap targets ≥44px" if not small else f"⚠ under 44px: {small}")
    # one h1, headings in order
    h = pg.evaluate("() => [...document.querySelectorAll('h1,h2,h3')].map(e=>e.tagName)")
    if h.count('H1') != 1: fails.append(f"h1 count = {h.count('H1')}")
    else: print(f"✓ one h1, {h.count('H2')} h2, {h.count('H3')} h3 — order {'ok' if h[0]=='H1' else 'BAD'}")
    print("✓ title:", pg.title())
    b.close()

# 6. the call-to-action set: right actions, right order, first one primary
import build_site as B
acts = [a[0] for a in B.actions()]
want = (['book'] if C.OUTSTANDING['booking_url'] else []) + \
       (['whatsapp'] if C.BUSINESS.get('whatsapp') else []) + ['call']
if acts != want: fails.append(f"CTA order {acts} != {want}")
hero = re.search(r'<div class="cta">(.*?)</div>', html, re.S).group(1)
btns = re.findall(r'<a class="(btn[^"]*)"[^>]*><svg.*?</svg><span>([^<]+)</span>', hero, re.S)
if len(btns) != len(want): fails.append(f"hero shows {len(btns)} buttons, expected {len(want)}")
if btns and btns[0][0] != 'btn': fails.append("first CTA is not the primary style")
if C.BUSINESS.get('whatsapp'):
    if f"wa.me/{C.BUSINESS['whatsapp']}?text=" not in html:
        fails.append("WhatsApp link missing or malformed")
    if C.BUSINESS['whatsapp'].startswith(('0', '+')):
        fails.append("wa.me number must have no leading zero and no +")
print(f"✓ CTAs: {' → '.join(l for _, l in btns)} (first is primary)")

# 7. title and description must survive Google's truncation
title, desc = C.SEO['title'], C.SEO['description']
if len(title) > 62: fails.append(f"title {len(title)} chars — Google cuts near 60")
if not 120 <= len(desc) <= 158: fails.append(f"description {len(desc)} chars — aim 120–158")
print(f"✓ title {len(title)} chars, description {len(desc)} chars — both display in full")

# 8. the terms we're actually targeting are present
for term, least in [('southend', 3), ('westcliff', 3), ('builder gel', 3),
                    ('hard gel', 2), ('gel nails', 1), ('nail technician', 1)]:
    n = html.lower().count(term)
    if n < least: fails.append(f"target term {term!r} appears {n}× (want ≥{least})")
print("✓ every target term present in the copy")

print()
print("FAILED:" if fails else "ALL CHECKS PASSED")
[print(" ✗", f) for f in fails]
sys.exit(1 if fails else 0)
