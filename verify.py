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
for group, _blurb, items in C.GROUPS:
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
listed = {k for _, _b, items in C.GROUPS for k, _ in items}
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
    # Scroll the whole page before judging images. The gallery is lazy-loaded,
    # so anything below the fold never starts fetching in a viewport that
    # never moves — and would be reported broken when it is merely unread.
    # Scrolling is also what a real visitor does, so this tests the real thing.
    #
    # Two things this has to get right, both learned the hard way:
    #
    #  1. scrollHeight is re-read every step. The page GROWS as lazy images
    #     arrive and reserve their space, so a height snapshotted at the top
    #     stops short of the real bottom. At five photos the shortfall was
    #     invisible; at fourteen it left the last two unread and reported them
    #     broken.
    #  2. The wait afterwards is on the images themselves, not on a stopwatch.
    #     A fixed timeout is a guess about network and decode speed that gets
    #     wronger every time the gallery grows.
    pg.evaluate("""async () => {
        const pause = ms => new Promise(r => setTimeout(r, ms));
        let y = 0;
        for (let guard = 0; guard < 200; guard++) {
            window.scrollTo(0, y);
            await pause(120);
            if (y >= document.body.scrollHeight - window.innerHeight) break;
            y += window.innerHeight * 0.8;
        }
        // Settle at the bottom so the final row is definitely in view, then
        // wait for every image to finish rather than for a fixed interval.
        window.scrollTo(0, document.body.scrollHeight);
        const deadline = Date.now() + 15000;
        while (Date.now() < deadline) {
            if ([...document.images].every(i => i.complete)) break;
            await pause(100);
        }
        window.scrollTo(0, 0);
    }""")
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

# 6b. gallery detail panels: one per photograph, every word on the page, and
#     the level price matching the booking menu rather than a typed-in copy.
g = C.OUTSTANDING['gallery']
for i, x in enumerate(g, 1):
    if not x.get('note', '').strip():
        fails.append(f"gallery {x['file']} has no note — nothing to show when tapped")
    if f'id="set-{i}"' not in html:
        fails.append(f"no detail panel for set-{i} ({x['file']})")
    if f'href="#set-{i}"' not in html:
        fails.append(f"set-{i} has a panel but no tile links to it")
    if x.get('note') and x['note'][:40] not in html:
        fails.append(f"note not rendered for {x['file']}")
    lvl = x.get('level')
    if lvl not in (None, 1, 2, 3):
        fails.append(f"{x['file']} has level {lvl!r} — must be 1, 2, 3 or None")
    if lvl:
        want = src[C.ART_LEVELS[lvl]['service']]['price'].replace('.00', '')
        if f'{want} added to any service' not in html:
            fails.append(f"{x['file']} is Level {lvl} but {want} is not shown for it")
# an orphan panel is as bad as a missing one — it would be dead HTML Google reads
for stray in re.findall(r'id="set-(\d+)"', html):
    if int(stray) > len(g):
        fails.append(f"panel set-{stray} has no photograph behind it")
lvls = [x.get('level') for x in g]
print(f"✓ {len(g)} detail panels — {lvls.count(3)}× Level 3, {lvls.count(2)}× Level 2, "
      f"{lvls.count(1)}× Level 1, {lvls.count(None)}× no art")

# the whole feature depends on there being no JavaScript, because the site's
# own CSP forbids it. If a script tag ever appears, the CSP will silently
# kill it and the panels will look broken to everyone but the person who
# added it.
if re.search(r'<script(?![^>]*type="application/ld\+json")', html):
    fails.append("a <script> tag appeared — CSP sets script-src 'none', it will not run")

# 6c. every gallery photograph must carry the watermark, and the portrait
#     must not. If watermark.py ever fails quietly — a missing brand asset,
#     a copy that skips the stamp — the images still load and the page still
#     looks right, so nothing else here would notice.
#
#     This measures HOW MUCH the corner changed, not whether it changed at
#     all. The first version of this check asked "do any pixels differ" and
#     passed a build whose stamp was a no-op: re-saving a JPEG re-encodes it,
#     so a handful of pixels differ everywhere even when nothing was drawn.
#     Measured across the gallery: a real stamp moves the corner 5.3-15.4
#     mean absolute levels, re-encoding alone moves it 0.00-0.38. The floor
#     below sits between those.
#
#     Re-measured twice since. The mark went white, small and light, and the
#     signal fell from 15.4 to 4.79; then the mark became the monogram alone
#     and it fell again. Each time the threshold had to move with it, which
#     is the standing hazard with a measured check: quieten the thing being
#     measured and the check keeps passing right up until it silently stops
#     meaning anything.
#
#     It also used to look only at the bottom-right corner. The stamp now
#     picks whichever corner is clearest, so ten of nineteen moved and this
#     check failed them all — correctly, on its own stale assumption. It now
#     scans all four and takes the strongest, with the middle of the frame
#     as the control, because the mark is never placed there.
from PIL import Image, ImageChops, ImageStat
import config as _C

# Measured with the logo in brand colour: signal 9.03-20.33, re-encoding
# noise up to 0.50. 2.1 is the balance point, unchanged.
#
# SEVENTH value. 15.4 -> 4.79 -> 4.35 -> 8.93 -> 8.54 -> 13.20 -> 20.33, as
# the mark went white, small, to the wordmark, lost its NAILS BY line, got
# it back at brand size, then went to full brand colour. Not one of those
# moves made the check fail on its own. That is the trap with a measured
# threshold: it does not fail when it goes stale, it just quietly stops
# meaning anything. Re-measure whenever the mark changes.
STAMP_FLOOR = 2.1

def _corners(im):
    w, h = im.size
    cw, ch = int(w * .34), int(h * .26)
    return [im.crop((w - cw, h - ch, w, h)), im.crop((0, h - ch, cw, h)),
            im.crop((w - cw, 0, w, ch)),     im.crop((0, 0, cw, ch))]

def _centre(im):
    w, h = im.size
    return im.crop((int(w * .3), int(h * .35), int(w * .7), int(h * .65)))

def _mad(a, b):
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]

stamped, weakest = 0, None
for entry in _C.OUTSTANDING['gallery']:
    f = entry['file']
    master_p = pathlib.Path('photos') / f
    stem, suffix = f.rsplit('.', 1)
    hits = sorted(pathlib.Path('public/img').glob(f'{stem}.*.{suffix}'))
    if len(hits) != 1:
        fails.append(f"expected exactly one published {stem}.<hash>.{suffix}, found {len(hits)}")
        continue
    built_p = hits[0]
    master = Image.open(master_p).convert('RGB')
    built = Image.open(built_p).convert('RGB')
    corner = max(_mad(a, b) for a, b in zip(_corners(master), _corners(built)))
    control = _mad(_centre(master), _centre(built))
    if corner < STAMP_FLOOR:
        fails.append(f"{f} is published unwatermarked — no corner moved more than "
                     f"{corner:.2f}, below the {STAMP_FLOOR} floor")
    elif corner <= control * 3:
        fails.append(f"{f} corner moved {corner:.2f} but so did the middle of the "
                     f"frame ({control:.2f}) — that is re-encoding, not a stamp")
    else:
        stamped += 1
        weakest = corner if weakest is None else min(weakest, corner)

p = _C.OUTSTANDING.get('portrait')
if p:
    pstem, psuf = p['file'].rsplit('.', 1)
    phits = sorted(pathlib.Path('public/img').glob(f'{pstem}.*.{psuf}'))
    a = Image.open(pathlib.Path('photos') / p['file']).convert('RGB')
    b = Image.open(phits[0]).convert('RGB') if phits else a
    if max(_mad(x, y) for x, y in zip(_corners(a), _corners(b))) >= STAMP_FLOOR:
        fails.append("the portrait has been watermarked — it is Maddy's own face "
                     "on her own site and should not carry a stamp")
if stamped:
    print(f"✓ {stamped} gallery photographs watermarked (weakest {weakest:.1f} vs "
          f"{STAMP_FLOOR} floor), portrait left clean")
else:
    print("✗ no gallery photograph carries a watermark")

# 6d. every photograph the page links to must carry a hash of its own bytes.
#     They are served max-age=31536000, immutable — a promise that the bytes
#     behind the URL never change. Under fixed filenames that promise was
#     false: nineteen photographs were rewritten under the names they already
#     had, so any cache holding the old copy would serve it for a year. This
#     recomputes the hash from the published file and fails if the name does
#     not match, because a stale photograph on a launched site is invisible
#     from here — it looks fine to whoever deployed it and wrong to everyone
#     whose edge kept the old one.
import hashlib
linked = set(re.findall(r'src="(img/[^"]+\.jpg)"', html))
if not linked:
    fails.append("no photographs are linked from the page at all")
for rel in sorted(linked):
    f = pathlib.Path('public') / rel
    if not f.exists():
        fails.append(f"page links {rel}, which was not published")
        continue
    parts = f.stem.rsplit('.', 1)
    if len(parts) != 2 or len(parts[1]) != 8:
        fails.append(f"{rel} has no content hash in its name, but is served immutable")
        continue
    want = hashlib.sha256(f.read_bytes()).hexdigest()[:8]
    if parts[1] != want:
        fails.append(f"{rel} is named for hash {parts[1]} but its bytes hash to {want}")
print(f"✓ {len(linked)} photographs carry a hash of their own bytes (safe to serve immutable)")

# 6e. the price list must read as a menu, not a list: a heading with no
#     sentence under it tells a first-timer nothing, and the products block
#     is where the two questions a careful client actually asks get answered
#     — what is going on my nails, and will it set me off.
for group, blurb, _items in C.GROUPS:
    if not blurb.strip():
        fails.append(f"price group {group!r} has no description")
    elif blurb[:40] not in html:
        fails.append(f"description for {group!r} is not on the page")
pr = C.PRODUCTS
for key in ('heading', 'body', 'highlight', 'aside'):
    if not pr.get(key, '').strip():
        fails.append(f"PRODUCTS[{key!r}] is empty")
    elif pr[key][:40] not in html:
        fails.append(f"PRODUCTS[{key!r}] is not rendered on the page")
# The HEMA line must keep its own block. Folded into a paragraph it stops
# being an answer and goes back to being a detail.
if 'class="hema"' not in html:
    fails.append("the HEMA / HEMA-free line has lost its highlighted block")
# Products she does not use must never appear as hers — BIAB is The Gel
# Bottle Inc's trademark and the first FAQ exists to explain the difference.
for brand in ('Twenty Pro', 'American Creator'):
    if brand not in html:
        fails.append(f"{brand} is not named anywhere on the page")
print(f"✓ {len(C.GROUPS)} price groups each carry a description; "
      f"products block and HEMA highlight both render")

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
