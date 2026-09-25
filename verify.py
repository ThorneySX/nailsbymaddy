import json, re, pathlib, sys
import datetime as _dt
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
blob = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
# The schema is now ONE @graph whose entities cross-reference each other by
# @id, rather than a list of unrelated top-level objects. Google reads both,
# but only the graph lets the salon, the person, the photographs and the
# breadcrumb say they are about each other — which is what an entity is.
# Accept the old shape too so this file does not break mid-refactor.
if isinstance(blob, dict) and '@graph' in blob:
    graphs = blob['@graph']
elif isinstance(blob, dict):
    graphs = [blob]
else:
    graphs = blob
by_type = {}
for g in graphs:
    ty = g.get('@type')
    for one in (ty if isinstance(ty, list) else [ty]):
        by_type.setdefault(one, g)
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
# Book Now is always first and always present. WhatsApp only appears as a
# second button once booking_url points somewhere else — before that, Book Now
# IS the WhatsApp link and a second button would be the same destination twice.
# The call button was removed on 25 Sept 2026; the number lives in the footer,
# the 404 and `telephone` in the schema, where Google reads it for NAP matching.
want = ['book']
if C.OUTSTANDING['booking_url'] and C.BUSINESS.get('whatsapp'):
    want.append('whatsapp')
if acts != want: fails.append(f"CTA order {acts} != {want}")
if 'tel:' in re.search(r'<div class="cta">(.*?)</div>', html, re.S).group(1):
    fails.append("a tel: link is back in the hero CTA — the call button was removed deliberately")
if f'tel:{C.BUSINESS["phone_e164"]}' not in html:
    fails.append("the phone number has vanished from the page entirely — it belongs in the footer")
hero = re.search(r'<div class="cta">(.*?)</div>', html, re.S).group(1)
btns = re.findall(r'<a class="(btn[^"]*)"[^>]*><svg.*?</svg><span>([^<]+)</span>', hero, re.S)
if len(btns) != len(want): fails.append(f"hero shows {len(btns)} buttons, expected {len(want)}")
if btns and btns[0][0] != 'btn': fails.append("first CTA is not the primary style")
if C.BUSINESS.get('whatsapp'):
    # Whether it is behind "Book Now" or its own button, the wa.me link must
    # be well-formed — a leading zero or a + silently opens an empty chat.
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

# 6f. the section nav must actually go somewhere. The page is long on a
#     phone — nineteen photographs, twenty prices, six FAQs — so every nav
#     link pointing at a section that exists is the difference between
#     finding the prices and scrolling past them. A dead nav link is worse
#     than no nav at all.
nav_targets = re.findall(r'<nav class="nav".*?</nav>', html, re.S)
if not nav_targets:
    fails.append("the section nav is missing")
else:
    links = re.findall(r'href="#([^"]+)"', nav_targets[0])
    if len(links) < 4:
        fails.append(f"section nav has only {len(links)} links")
    for t in links:
        if f'id="{t}"' not in html:
            fails.append(f"nav links to #{t}, which is not on the page")
    print(f"✓ section nav: {len(links)} links, every target exists")

# The burger is an anchor and the nav is its :target. With no JavaScript that
# pairing IS the menu, so a renamed id silently leaves the nav permanently
# shut — and shut is the default, so nobody would notice on a desktop.
if 'href="#menu"' not in html or 'id="menu"' not in html:
    fails.append("burger href and nav id no longer match — the menu cannot open")
if 'class="nav-close"' not in html:
    fails.append("no way to close the menu without choosing a section")
if 'class="totop"' not in html or 'href="#top"' not in html:
    fails.append("back-to-top link missing")
if 'id="top"' not in html:
    fails.append("back-to-top points at #top, which does not exist")

# 6g. supplier marks: shown as supplied, and never altered. They are other
#     companies' trademarks — the one thing we control is that we do not
#     recolour, restyle or watermark them, and that the page claims no
#     partnership it does not have.
for x in C.PRODUCTS.get('suppliers', []):
    src = pathlib.Path('brand/suppliers') / x['file']
    built = pathlib.Path('public/img/suppliers') / x['file']
    if not built.exists():
        fails.append(f"supplier mark {x['file']} was not published")
    elif src.read_bytes() != built.read_bytes():
        fails.append(f"supplier mark {x['file']} was altered on the way out — "
                     f"these are published byte-for-byte as supplied")
    if x['alt'] not in html:
        fails.append(f"supplier mark {x['file']} has no alt text on the page")
# No claim of a relationship that does not exist. Scanned against the VISIBLE
# text only — the first version searched the whole file and tripped on the
# word "partner" inside a CSS comment explaining that we do not claim to be
# one, which is a check failing on its own documentation.
_visible = re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', html, flags=re.S)
_visible = re.sub(r'<!--.*?-->', ' ', _visible, flags=re.S)
_visible = re.sub(r'<[^>]+>', ' ', _visible).lower()
for word in ('partner', 'official stockist', 'approved by', 'endorsed'):
    if word in _visible:
        fails.append(f"page says {word!r} near the supplier marks — no such "
                     f"relationship has been agreed")
print(f"✓ {len(C.PRODUCTS.get('suppliers', []))} supplier marks published "
      f"unaltered, no partnership claimed")

# 7. title and description must survive Google's truncation
title, desc = C.SEO['title'], C.SEO['description']
if len(title) > 62: fails.append(f"title {len(title)} chars — Google cuts near 60")
if not 120 <= len(desc) <= 158: fails.append(f"description {len(desc)} chars — aim 120–158")
print(f"✓ title {len(title)} chars, description {len(desc)} chars — both display in full")

# 8. the terms we're actually targeting are present
import html as _H
_body = re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', html, flags=re.S)
_body = _H.unescape(re.sub(r'<[^>]+>', ' ', _body)).lower()
# Counted in the VISIBLE COPY, not the file. The first version of this counted
# the whole of index.html, so "nail technician" scored a pass on the strength
# of the JSON-LD and the alt attributes while appearing nowhere a reader could
# see it — a term Google reads in the body is a term the page is about; a term
# only in the markup is a claim about the page.
for term, least in [('southend', 3), ('westcliff', 3), ('builder gel', 3),
                    ('hard gel', 2), ('gel nails', 1), ('nail technician', 1),
                    ('essex', 1)]:
    n = _body.count(term)
    if n < least: fails.append(f"target term {term!r} appears {n}× in the visible copy (want ≥{least})")
print(f"✓ every target term present in the visible copy ({len(_body.split())} words)")

# 9. the @graph must hold together. Its whole value over a pile of loose
#    objects is that entities point at each other by @id — so a reference to
#    an @id nothing defines is worse than no reference at all: it looks like
#    a relationship and resolves to nothing. This walks every {"@id": ...}
#    reference in the graph and checks something in the graph answers to it.
defined = {g['@id'] for g in graphs if '@id' in g}
def _refs(node, out):
    if isinstance(node, dict):
        if set(node) == {'@id'}: out.add(node['@id'])
        else:
            for v in node.values(): _refs(v, out)
    elif isinstance(node, list):
        for v in node: _refs(v, out)
    return out
dangling = _refs(graphs, set()) - defined
if dangling: fails.append(f"schema @id references nothing defines: {sorted(dangling)}")

for want in ('NailSalon', 'Person', 'WebSite', 'WebPage', 'BreadcrumbList',
             'FAQPage', 'ImageObject', 'Organization'):
    if want not in by_type: fails.append(f"schema is missing a {want} entity")

# Google matches the site's NAP against the Google Business Profile, and the
# coordinates are what put the pin in the right place. They were verified
# against postcodes.io rather than typed.
geo = ld.get('geo', {})
if geo.get('@type') != 'GeoCoordinates' or not geo.get('latitude'):
    fails.append("NailSalon has no GeoCoordinates — the local pin has nothing to sit on")
for f in ('telephone', 'address', 'openingHoursSpecification', 'priceRange'):
    if f not in ld: fails.append(f"NailSalon schema is missing {f}")
if 'aggregateRating' in ld:
    fails.append("aggregateRating is in the schema — self-serving ratings are against "
                 "Google's policy and AGENTS.md forbids it")
# The booking action must point wherever Book Now points today, or the
# structured data promises a booking route the page does not offer.
pa = ld.get('potentialAction', {})
if pa.get('@type') != 'ReserveAction':
    fails.append("no ReserveAction — nothing in the schema says she can be booked")
elif B.book_href() not in json.dumps(pa):
    fails.append("ReserveAction target does not match where Book Now actually goes")

imgs = [g for g in graphs if g.get('@type') == 'ImageObject']
# Attribution is required on the PHOTOGRAPHS — they are the work, they are what
# gets lifted, and Google shows creator and credit in the Images viewer. The
# logo is a brand mark, not a licensable photograph, and the portrait is
# Maddy's own face: neither is on offer, so neither carries acquireLicensePage.
#
# NOTE: Google's licensable-image badge needs a `license` URL pointing at
# written terms. There is no such page, so the badge will not appear; what is
# here is the attribution metadata, which it does read. Adding terms is a
# decision for Maddy, not a build change.
for i in imgs:
    aid = i.get('@id', '')
    need = ['contentUrl']
    if not aid.endswith('#logo'):
        need += ['creator', 'copyrightNotice', 'creditText']
    if aid.startswith(f'{C.SITE_URL}/#image-'):
        need += ['acquireLicensePage']
    for f in need:
        if f not in i: fails.append(f"ImageObject {aid} has no {f}")
print(f"✓ schema @graph: {len(graphs)} entities, {len(imgs)} ImageObjects, "
      f"every @id reference resolves")

# 9b. the footer credit. This is a case-study build; the line is the return.
cr = C.CREDIT
for k in ('builder', 'builder_url', 'parent', 'parent_url'):
    if not cr.get(k): fails.append(f"CREDIT[{k!r}] is empty")
foot = re.search(r'<p class="fine">(.*?)</p>', html, re.S)
if not foot:
    fails.append("footer credit line is missing entirely")
else:
    f = foot.group(1)
    for bit in (f"&copy; {_dt.date.today().year}", C.BUSINESS['name'],
                cr['builder'], cr['builder_url'], 'part of the',
                cr['parent'], cr['parent_url']):
        if bit not in f: fails.append(f"footer credit does not carry {bit!r}")
    print("✓ footer credit: © {}, site by {}, part of the {} — both linked".format(
        _dt.date.today().year, cr['builder'], cr['parent']))

# 9c. the sitemap must parse, list this page, and point only at files that
#     exist. A sitemap that names a 404 is the fastest way to teach Search
#     Console to distrust the rest of it.
import xml.etree.ElementTree as ET
sm = pathlib.Path('public/sitemap.xml')
if not sm.exists():
    fails.append("no sitemap.xml was written")
else:
    NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'i': 'http://www.google.com/schemas/sitemap-image/1.1'}
    try:
        root = ET.fromstring(sm.read_text())
    except ET.ParseError as e:
        root = None; fails.append(f"sitemap.xml is not well-formed XML: {e}")
    if root is not None:
        locs = [u.findtext('s:loc', namespaces=NS) for u in root.findall('s:url', NS)]
        if locs != [f"{C.SITE_URL}/"]:
            fails.append(f"sitemap lists {locs}, expected just the one page")
        ilocs = [e.text for e in root.iter('{%s}loc' % NS['i'])]
        for u in ilocs:
            rel = u.replace(C.SITE_URL + '/', '')
            if not (pathlib.Path('public') / rel).exists():
                fails.append(f"sitemap names {rel}, which was not published")
        # Deprecated since May 2022 and unread since that August. Their
        # presence is not an error, it is a claim that they do something.
        for dead in ('title', 'caption', 'geo_location', 'license'):
            if root.find('.//{%s}%s' % (NS['i'], dead)) is not None:
                fails.append(f"sitemap still emits image:{dead} — Google dropped it in 2022")
        if root.find('.//{%s}changefreq' % NS['s']) is not None or \
           root.find('.//{%s}priority' % NS['s']) is not None:
            fails.append("sitemap carries changefreq/priority — Google ignores both")
        n_page_imgs = len(set(re.findall(r'src="(img/[^"]+)"', html)))
        print(f"✓ sitemap: 1 URL, {len(ilocs)} images, all present on disk, "
              f"no deprecated fields")

# 9d. filenames have to earn their place in Google Images. A photograph
#     published as work-07.jpg tells a crawler nothing; the alt text is the
#     other half and neither substitutes for the other.
STOP = {'and', 'the', 'with', 'a', 'in', 'on', 'of'}
for x in C.OUTSTANDING['gallery'] + [C.OUTSTANDING['portrait']]:
    stem = x['file'].rsplit('.', 1)[0]
    if re.fullmatch(r'(work|img|photo|image|dsc|IMG)[-_]?\d+', stem):
        fails.append(f"{x['file']} is still a camera filename — no keywords in it")
    words = [w for w in stem.split('-') if w and w not in STOP]
    if len(words) < 4:
        fails.append(f"{x['file']} carries only {len(words)} descriptive words in its name")
    if len(stem) > 70:
        fails.append(f"{x['file']} name is {len(stem)} chars — keep it readable")
    alt = x.get('alt', '')
    if len(alt) < 25:
        fails.append(f"{x['file']} alt text is {len(alt)} chars — too thin to describe anything")
    if len(alt) > 160:
        fails.append(f"{x['file']} alt text is {len(alt)} chars — screen readers will not thank us")
    if alt.lower().startswith(('image of', 'picture of', 'photo of')):
        fails.append(f"{x['file']} alt text opens with 'image of' — the tag already says that")
print(f"✓ {len(C.OUTSTANDING['gallery'])+1} images: keyword filenames and "
      f"descriptive alt text, none of it boilerplate")

# 9e. every master photograph must have its ORIGINAL's fingerprint recorded.
#     dedupe.py compares a candidate's full frame against these, so a missing
#     entry does not break anything — it just quietly stops catching re-sends
#     of that one set, which is the failure mode that costs a round trip to
#     Maddy and risks the same nails appearing twice on a live page. It went
#     missing once already, when a file was renamed and the key was not.
srcs = json.loads(pathlib.Path('photos/sources.json').read_text())
masters = {p.name for p in pathlib.Path('photos').glob('*.jpg')}
for m in sorted(masters - set(srcs)):
    fails.append(f"photos/sources.json has no source fingerprint for {m} — "
                 f"dedupe will not catch a re-send of it")
for s in sorted(set(srcs) - masters):
    fails.append(f"photos/sources.json names {s}, which is not in photos/")
print(f"✓ {len(srcs)} source fingerprints, one per master photograph")

print()
print("FAILED:" if fails else "ALL CHECKS PASSED")
[print(" ✗", f) for f in fails]
sys.exit(1 if fails else 0)
