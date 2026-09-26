#!/usr/bin/env python3
"""
Builds public/ — the whole Nails by Maddy site.

  python3 build_site.py

Output is a static site served by a Cloudflare Worker. One page, no JS
framework, no build step beyond this file. Fonts and logos are copied in
from the brand pack so the site never calls a third party.
"""
import html as H
import json
import re
import datetime as _dt
import shutil
from pathlib import Path

import config as C

ROOT = Path(__file__).parent
BRAND = ROOT / "brand"                   # logo masters, vendored
PHOTOS = ROOT / "photos"                 # Maddy's own photographs, as supplied
PUB = ROOT / "public"                    # generated — never edit, never committed
NODE = ROOT / "node_modules/@fontsource"

# Photograph filename -> the content-hashed name actually published. Filled by
# copy_assets(); img() reads it. Empty until then, which is why copy_assets
# runs before any HTML is built.
ASSETS = {}

# Published names for the three brand images a search engine actually reads.
LOGO       = "img/nails-by-maddy-logo.svg"
LOGO_WHITE = "img/nails-by-maddy-logo-white.svg"
SHARE      = "img/nails-by-maddy-nail-technician-westcliff-southend.png"


def img(name):
    """The published path for a photograph, with its content hash."""
    if name not in ASSETS:
        raise SystemExit(
            f"img({name!r}) called before copy_assets() published it — "
            f"the hashed name is only known once the file is written."
        )
    return f"img/{ASSETS[name]}"

esc = lambda s: H.escape(str(s), quote=False)


# ------------------------------------------------------------------- assets

def copy_assets():
    for d in ("fonts", "img"):
        (PUB / d).mkdir(parents=True, exist_ok=True)

    for pkg, faces in (("outfit", ["400", "500", "600", "700"]), ("shrikhand", ["400"])):
        for w in faces:
            src = NODE / pkg / "files" / f"{pkg}-latin-{w}-normal.woff2"
            shutil.copy(src, PUB / "fonts" / src.name)

    for name, dest in [
        # Published names are keyword-bearing where a search engine will ever
        # read them, and conventional where a BROWSER looks them up by path.
        # favicon.png and apple-touch-icon.png stay put: Safari and assorted
        # crawlers probe those exact paths, and no one has ever searched for a
        # favicon. The logo and the share card are different — both surface in
        # image search and in link previews.
        ("nailsbymaddy-logo-primary.svg", LOGO),
        ("nailsbymaddy-logo-reversed.svg", LOGO_WHITE),
        ("nailsbymaddy-icon-32.png", "favicon.png"),
        ("nailsbymaddy-icon-180.png", "apple-touch-icon.png"),
        ("nailsbymaddy-icon-512.png", "img/nails-by-maddy-icon-512.png"),
        ("nailsbymaddy-profile-badge.png", SHARE),
    ]:
        shutil.copy(BRAND / name, PUB / dest)

    # Maddy's photographs. Only the ones config actually references are copied,
    # so a stray file in photos/ cannot end up published by accident, and a
    # filename that config names but photos/ does not hold fails the build here
    # rather than shipping a broken image.
    #
    # Gallery photographs are watermarked on the way through; photos/ holds
    # clean masters. The portrait is NOT stamped — it is Maddy's own face on
    # Maddy's own site, and a watermark there would read as a stock photo,
    # which is the opposite of what it is for.
    import hashlib
    import watermark

    wanted = [p["file"] for p in C.OUTSTANDING["gallery"]]
    portrait = C.OUTSTANDING["portrait"]["file"] if C.OUTSTANDING["portrait"] else None
    if portrait:
        wanted.append(portrait)
    for f in wanted:
        src = PHOTOS / f
        if not src.exists():
            raise SystemExit(f"config names photos/{f}, which does not exist")
        tmp = PUB / "img" / f
        if f == portrait:
            shutil.copy(src, tmp)
        else:
            watermark.stamp_file(src, tmp)

        # Rename to include a hash of the finished bytes, and remember the
        # mapping so the page can link to it.
        #
        # These files are served with max-age=31536000, immutable — a year,
        # and a promise to the browser and to every Cloudflare edge that the
        # bytes behind this URL will never change. Under a fixed filename
        # that promise was a lie: all nineteen photographs were rewritten
        # today under the names they already had, so anyone holding
        # yesterday's copy keeps it until 2027. Content in the name makes
        # the promise true — change the picture and it is a different URL.
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()[:8]
        final = f"{tmp.stem}.{digest}{tmp.suffix}"
        tmp.rename(PUB / "img" / final)
        ASSETS[f] = final

    # Supplier marks, copied as supplied. Not watermarked, not recoloured —
    # they are other companies' trademarks and we alter nothing about them.
    sup_src = BRAND / "suppliers"
    if sup_src.is_dir():
        (PUB / "img" / "suppliers").mkdir(parents=True, exist_ok=True)
        for x in C.PRODUCTS.get("suppliers", []):
            f = sup_src / x["file"]
            if not f.exists():
                raise SystemExit(f"config names a supplier mark that is missing: {f}")
            shutil.copy(f, PUB / "img" / "suppliers" / x["file"])

    optimise_svg()


def optimise_svg():
    """
    The wordmarks are outlined type at full float precision — 37 KB each.
    svgo at 2dp takes them to 9 KB with no visible change (checked pixel by
    pixel: 0.05% of pixels differ, all edge antialiasing). Skipped silently
    if svgo isn't installed, so the build never depends on it.
    """
    import subprocess
    cfg = ROOT / "svgo.config.mjs"
    if not cfg.exists():
        return
    try:
        subprocess.run(["npx", "--yes", "svgo", "--config", str(cfg), "-f", str(PUB / "img")],
                       check=True, capture_output=True, timeout=120)
    except Exception as e:
        print(f"  (svg optimisation skipped: {type(e).__name__})")


def logo_img(file=LOGO, cls="logo", eager=True):
    """
    The wordmark is outlined type — 37 KB of path data. Inlining two of those
    would put 74 KB of SVG in front of the parser, so they stay as files:
    cached, fetched in parallel, and sized here so nothing shifts while loading.
    """
    w, h = svg_box(PUB / file)
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img class="{cls}" src="{file}" alt="Nails by Maddy" '
            f'width="{w}" height="{h}" {load} decoding="async">')


def svg_box(path):
    """Intrinsic size, so we can reserve the space and avoid layout shift."""
    head = path.read_text()[:600]
    m = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', head)
    if m:
        return round(float(m.group(1))), round(float(m.group(2)))
    m = re.search(r'width="([\d.]+)".*?height="([\d.]+)"', head, re.S)
    return (round(float(m.group(1))), round(float(m.group(2)))) if m else (600, 200)


# -------------------------------------------------------------------- prices

def services():
    return {s["title"]: s for s in json.loads((ROOT / "services.json").read_text())}


def price_html():
    sv, out = services(), []
    for group, blurb, items in C.GROUPS:
        rows = "".join(
            f'<div class="row"><dt>{esc(label)}'
            f'<span class="dur">{esc(sv[key]["dur"])}</span></dt>'
            f'<dd>{esc(sv[key]["price"].replace(".00", ""))}</dd></div>'
            for key, label in items
        )
        out.append(f'<h3 class="grp">{esc(group)}</h3>'
                   f'<p class="grp-note">{esc(blurb)}</p>'
                   f'<dl class="prices">{rows}</dl>')

    # What she uses, and the line that lets a nervous client book.
    pr = C.PRODUCTS
    out.append(
        f'<div class="products">'
        f'<h3>{esc(pr["heading"])}</h3>'
        f'<p>{esc(pr["body"])}</p>'
        f'<p class="hema">{esc(pr["highlight"])}</p>'
        f'{supplier_row()}'
        f'<p class="aside">{esc(pr["aside"])}</p>'
        f'</div>'
    )
    return "".join(out)


# --------------------------------------------------------------- placeholders

def hold(label, note=""):
    """A visible gap, only ever rendered in draft mode."""
    if not C.DRAFT:
        return ""
    n = f'<span class="hold-note">{esc(note)}</span>' if note else ""
    return f'<div class="hold"><span class="hold-tag">To supply</span>{esc(label)}{n}</div>'


# ---------------------------------------------------------------- components

# Generic glyphs, not brand marks — a handset, a speech bubble, a calendar.
ICONS = {
    "call": '<path d="M5 3h3l2 5-2 1a12 12 0 0 0 5 5l1-2 5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
    "whatsapp": '<path d="M4 20l1.2-3.6A7.5 7.5 0 1 1 8 19.2z"/>',
    "book": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
}


def icon(kind):
    return (f'<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[kind]}</svg>')


def book_href():
    """Where "Book Now" actually sends someone, today.

    The booking system is an open commercial question — Maddy books through
    Kizuri's Ovatu account, so the booking record and the client relationship
    sit with the salon rather than with her. Until that is settled, the button
    says Book Now and opens WhatsApp, which is a channel she owns and which
    leaves her a written record of what was asked for.

    Fill OUTSTANDING["booking_url"] and the same button repoints itself. The
    label does not change, because the visitor's intent never did.
    """
    b, o = C.BUSINESS, C.OUTSTANDING
    if o["booking_url"]:
        return o["booking_url"]
    from urllib.parse import quote
    return f'https://wa.me/{b["whatsapp"]}?text={quote(b["whatsapp_msg"])}'


def actions():
    """
    Book Now first, WhatsApp second — and WhatsApp only once Book Now points
    somewhere else, or the page would carry the same link twice.

    THE CALL BUTTON WAS REMOVED, deliberately, on 25 Sept 2026. It used to be
    the permanent last option on the grounds that it is the only one that
    works for someone who does not use WhatsApp. Three buttons offering two
    destinations asked the visitor to make our unresolved decision for us; one
    button that says the thing they came to do does not.

    The number has NOT gone. It stays in the footer, in the 404 page and in
    `telephone` in the structured data, because Google matches the site's NAP
    against the Google Business Profile and a site with no phone number on it
    is a weaker local result, not a tidier one.
    """
    b, o = C.BUSINESS, C.OUTSTANDING
    out = [("book", book_href(), "Book Now", "Book an appointment with Maddy")]

    if o["booking_url"] and b.get("whatsapp"):
        from urllib.parse import quote
        href = f'https://wa.me/{b["whatsapp"]}?text={quote(b["whatsapp_msg"])}'
        out.append(("whatsapp", href, "WhatsApp", "Message Maddy on WhatsApp"))
    return out


def cta_row(align="center"):
    parts = []
    for i, (kind, href, label, aria) in enumerate(actions()):
        rel = ' rel="noopener"' if href.startswith("http") else ""
        cls = "btn" if i == 0 else "btn ghost"
        parts.append(f'<a class="{cls}" href="{href}" aria-label="{H.escape(aria)}"{rel}>'
                     f'{icon(kind)}<span>{esc(label)}</span></a>')
    html_ = "".join(parts)
    style = ' style="justify-content:flex-start"' if align == "left" else ""
    # No draft note. It was scaffolding addressed to us, printed on a page
    # the client reads — "Book online appears here once the booking system is
    # chosen" tells a visitor about our to-do list. What is outstanding lives
    # in config.py and in the README, which is where the people who can act
    # on it look. The page only ever shows what is true today.
    return f'<div class="cta"{style}>{html_}</div>'


def cta(label=None):
    """The single button in the sticky header — whatever the top action is."""
    kind, href, lab, aria = actions()[0]
    rel = ' rel="noopener"' if href.startswith("http") else ""
    return (f'<a class="btn" href="{href}" aria-label="{H.escape(aria)}"{rel}>'
            f'{icon(kind)}<span>{esc(label or lab)}</span></a>')


def _season_window(name, today):
    """The real dates of the occurrence of `name` that covers or next follows
    `today`, and whether it is in force now. Seasons are stored as (month, day)
    pairs so they repeat; winter wraps the new year, which is the only case
    worth care."""
    from datetime import date
    s = C.SEASONS[name]
    (sm, sd), (em, ed) = s["start"], s["end"]
    now, y = (today.month, today.day), today.year
    if (sm, sd) <= (em, ed):                      # sits inside one year
        return date(y, sm, sd), date(y, em, ed), (sm, sd) <= now <= (em, ed)
    if now >= (sm, sd):                           # wraps, and we are past the start
        return date(y, sm, sd), date(y + 1, em, ed), True
    return date(y - 1, sm, sd), date(y, em, ed), now <= (em, ed)


def hours_html():
    hrs = C.OUTSTANDING["hours"]
    if not hrs:
        return (hold("Opening hours", "her days and times at Kizuri")
                or '<p class="addr-note">Ring or message to book an appointment.</p>')
    # Group by day, keeping the given order, so a day with two seasonal windows
    # is one row with both rather than the same day appearing twice.
    order, by_day = [], {}
    for h in hrs:
        by_day.setdefault(h["day"], []) or order.append(h["day"])
        by_day[h["day"]].append(h)
    rows = []
    for day in order:
        parts = []
        for h in by_day[day]:
            # Season label FIRST, time last. With the label trailing, the
            # times on a seasonal day sat left of the column every other day
            # right-aligns to, so Thursday looked like a different table.
            t = f'{esc(h["open"])}–{esc(h["close"])}'
            lab = (f'<span class="season">{esc(C.SEASONS[h["season"]]["label"])}</span>'
                   if h.get("season") else '')
            # Each window is ONE element, so the dd can be a column of rows.
            # Left loose in the dd, the label and the time became two rows of
            # the flex column and the day read as two days.
            parts.append(f'<span class="win">{lab}<span class="hrs">{t}</span></span>')
        rows.append(f'<div class="row"><dt>{esc(day)}</dt>'
                    f'<dd>{"".join(parts)}</dd></div>')
    return f'<dl class="hours">{"".join(rows)}</dl>'


def supplier_row():
    """The suppliers' marks, on white cards.

    Not keyed to transparent: both marks sit on white in the files supplied,
    and the American Creator flag carries white stars and stripes, so removing
    white would punch holes straight through it. A white card is also how a
    stockist normally shows a supplier's mark.
    """
    sup = C.PRODUCTS.get("suppliers") or []
    if not sup:
        return ""
    tiles = "".join(
        f'<li><img src="img/suppliers/{esc(x["file"])}" alt="{H.escape(x["alt"])}" '
        f'loading="lazy" decoding="async" width="280" height="120"></li>'
        for x in sup
    )
    return f'<ul class="suppliers" aria-label="Products used">{tiles}</ul>'


def art_price(level):
    """The add-on price for an art level, read from the live booking menu.

    Never hard-coded. If Maddy changes what Level 3 costs in her booking
    system, services.json changes and every photograph that says 'Level 3'
    follows it. A price typed twice is a price that will disagree with
    itself eventually.
    """
    row = C.ART_LEVELS[level]
    src = {s["title"]: s for s in json.loads((ROOT / "services.json").read_text())}
    # Trailing .00 is dropped to match how every other price on the page is
    # written — the menu says £10, so the photograph says £10.
    return src[row["service"]]["price"].replace(".00", "")


def gallery_html():
    """The grid, plus one :target panel per photograph.

    Each tile is a link to an anchor; the panel for that anchor is hidden
    until it is the URL fragment, at which point CSS shows it over the page.
    No JavaScript — the site's own Content-Security-Policy sets
    script-src 'none', and it stays that way. Back button closes it, the
    panels are in the HTML so Google reads every word, and a visitor with
    CSS off still gets the photographs and the text, just in a long column.
    """
    g = C.OUTSTANDING["gallery"]
    if not g:
        return hold("Photographs of recent sets", "15–20 of her best, plus a portrait")

    tiles, panels = [], []
    for i, x in enumerate(g, 1):
        fid = f"set-{i}"
        alt = H.escape(x["alt"])
        lvl = x.get("level")

        if lvl:
            row = C.ART_LEVELS[lvl]
            tag = (f'<p class="lvl lvl-{lvl}"><b>{esc(row["label"])}</b> '
                   f'<span>{esc(row["blurb"])}</span> '
                   f'<em>{esc(art_price(lvl))} added to any service</em></p>')
            badge = f'<span class="badge b{lvl}" aria-hidden="true">L{lvl}</span>'
        else:
            tag = ('<p class="lvl lvl-0"><b>No art</b> '
                   '<span>a plain gel colour on natural nails</span></p>')
            badge = ""

        tiles.append(
            f'<figure class="tile"><a href="#{fid}">'
            f'<img src="{img(x["file"])}" alt="{alt}" loading="lazy" '
            f'decoding="async" width="600" height="600">{badge}'
            f'<span class="more" aria-hidden="true">+</span></a></figure>'
        )
        panels.append(
            f'<div class="lb" id="{fid}">'
            f'<a class="lb-back" href="#work" aria-label="Close"></a>'
            f'<div class="lb-card" role="dialog" aria-label="{alt}">'
            f'<img src="{img(x["file"])}" alt="{alt}" width="1200" height="1200">'
            f'<div class="lb-copy">{tag}<p class="lb-note">{esc(x["note"])}</p>'
            f'<a class="lb-x" href="#work">Close</a></div></div></div>'
        )

    return (f'<div class="grid">{"".join(tiles)}</div>'
            f'<p class="grid-hint">Tap any set to see what went into it.</p>'
            f'{"".join(panels)}')


def about_html():
    p = C.OUTSTANDING["portrait"]
    body = "".join(f"<p>{esc(t)}</p>" for t in C.ABOUT)
    q = C.OUTSTANDING["qualifications"]
    if q:
        body += f'<p class="quals">{esc(q)}</p>'
    else:
        body += hold("Qualifications and insurer", "for the about section")

    if p:
        pic = (f'<figure class="portrait"><img src="{img(p["file"])}" '
               f'alt="{H.escape(p["alt"])}" loading="lazy" decoding="async" '
               f'width="560" height="700"></figure>')
    else:
        pic = hold("Portrait of Maddy") or ""
    return f'<div class="about">{pic}<div class="about-copy">{body}</div></div>'


def faq_html():
    items = "".join(
        f'<details class="faq"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for q, a in C.FAQS
    )
    return f'<div class="faqs">{items}</div>'


def reviews_html():
    # The source is cited only when there is something a reader could go and
    # check. "Google" is that; the booking system is not — it is where we found
    # the review, not somewhere anyone can verify it, and printing it put the
    # internal words "Booking system" on a customer's screen the moment those
    # two reviews were cleared to publish. verify.py caught it as a leaked
    # internal note, correctly. Dressing it up as a badge would have been worse
    # than leaving it off: a provenance claim nobody can follow. So an empty
    # src prints the name alone, and no dangling separator with it.
    out = []
    for r in C.REVIEWS:
        if C.DRAFT or r["public"]:
            src = f' <span>· {esc(r["src"])}</span>' if r.get("src") else ""
            out.append(
                f'<blockquote class="quote"><p>{esc(r["text"])}</p>'
                f'<cite>{esc(r["who"])}{src}</cite></blockquote>'
            )
    note = hold("Permission to publish", "confirm with each client first") if C.DRAFT else ""
    return f'<div class="quotes">{"".join(out)}</div>{note}'


# ------------------------------------------------------------------ metadata

def image_objects():
    """One ImageObject per photograph, so Google Images has something to read.

    A filename and an alt attribute are all a crawler gets from the markup.
    An ImageObject adds the caption, the description, who took it and who owns
    it — which is what Google's image guidance asks for and what makes a
    photograph eligible to be shown with attribution rather than as an orphan
    thumbnail. It is also the only place the licence position is stated.
    """
    out = []
    for x in C.OUTSTANDING["gallery"]:
        url = f"{C.SITE_URL}/{img(x['file'])}"
        out.append({
            "@type": "ImageObject",
            "@id": f"{C.SITE_URL}/#image-{x['file'].rsplit('.', 1)[0]}",
            "contentUrl": url,
            "url": url,
            # The gallery panel this photograph opens, so the entity points at
            # a real fragment of a real page rather than at the file alone.
            "mainEntityOfPage": {"@id": f"{C.SITE_URL}/#webpage"},
            "name": x["alt"],
            "caption": x["alt"],
            "description": x["note"],
            "creator": {"@id": f"{C.SITE_URL}/#maddy"},
            "copyrightNotice": f"© {_dt.date.today().year} {C.BUSINESS['name']}",
            "creditText": C.BUSINESS["name"],
            "acquireLicensePage": f"{C.SITE_URL}/#find",
            "representativeOfPage": False,
            "width": 1200, "height": 1200,
        })
    pt = C.OUTSTANDING.get("portrait")
    if pt:
        url = f"{C.SITE_URL}/{img(pt['file'])}"
        out.append({
            "@type": "ImageObject",
            "@id": f"{C.SITE_URL}/#portrait",
            "contentUrl": url, "url": url,
            "name": pt["alt"], "caption": pt["alt"],
            "creator": {"@id": f"{C.SITE_URL}/#maddy"},
            "copyrightNotice": f"© {_dt.date.today().year} {C.BUSINESS['name']}",
            "creditText": C.BUSINESS["name"],
            "representativeOfPage": True,
        })
    return out


def schema():
    """
    One @graph, cross-referenced by @id, rather than a pile of unrelated
    islands. Google reads either, but the graph is the version that tells it
    these are all the SAME business, the SAME page and the SAME person — which
    is the whole point of publishing it for a one-page local site.

    NailSalon, not LocalBusiness — the more specific type wins.
    No aggregateRating: one review is not a rating, and self-serving review
    markup breaks Google's guidelines. For the same reason there is no
    `review` property either; a first-party review on your own business does
    not earn a rich result and it does invite a manual action.
    """
    b, cr = C.BUSINESS, C.CREDIT
    sv = services()
    offers = []
    for group, _blurb, items in C.GROUPS:
        for key, label in items:
            s = sv[key]
            offers.append({
                "@type": "Offer",
                "itemOffered": {
                    "@type": "Service",
                    "name": label,
                    "category": group,
                    "provider": {"@id": f"{C.SITE_URL}/#business"},
                    "areaServed": {"@type": "City", "name": "Southend-on-Sea"},
                },
                "price": s["price"].replace("£", "").replace(".00", ""),
                "priceCurrency": "GBP",
                "url": f"{C.SITE_URL}/#prices",
                "availability": "https://schema.org/InStock",
            })

    business = {
        "@type": "NailSalon",
        "@id": f"{C.SITE_URL}/#business",
        "name": b["name"],
        "url": C.SITE_URL + "/",
        "telephone": b["phone_e164"],
        "email": b["email"],
        "description": C.SEO["description"],
        "logo": {"@id": f"{C.SITE_URL}/#logo"},
        # The share card first, then the real photographs. Google reads
        # `image` for the knowledge panel and for image search, and nineteen
        # pieces of her own work say more than one generic card.
        "image": ([f"{C.SITE_URL}/{SHARE}"] +
                  [f"{C.SITE_URL}/{img(x['file'])}" for x in C.OUTSTANDING["gallery"]]),
        "priceRange": "££",
        "currenciesAccepted": "GBP",
        "address": {
            "@type": "PostalAddress",
            "name": b["venue"],
            "streetAddress": b["street"],
            "addressLocality": b["town"],
            "addressRegion": b["county"],
            "postalCode": b["postcode"],
            "addressCountry": b["country"],
        },
        # ONS postcode centroid — see the note in config.BUSINESS. Publishing a
        # point that is a few metres out is worth far more than publishing none,
        # because it is what lets Google reconcile this page with the map pin.
        "geo": {"@type": "GeoCoordinates",
                "latitude": b["lat"], "longitude": b["lon"]},
        "hasMap": b["maps"],
        "areaServed": [{"@type": "City", "name": n}
                       for n in ("Westcliff-on-Sea", "Southend-on-Sea", "Leigh-on-Sea", "Chalkwell")],
        "sameAs": [f"https://www.instagram.com/{b['instagram']}/", b["maps"]],
        "founder": {"@id": f"{C.SITE_URL}/#maddy"},
        "employee": {"@id": f"{C.SITE_URL}/#maddy"},
        "knowsAbout": ["Gel nails", "Builder gel", "Hard gel overlays",
                       "Nail art", "Spa pedicures", "Natural nail care"],
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Treatments",
            "itemListElement": offers,
        },
    }
    if C.OUTSTANDING["hours"]:
        # Only the window actually in force is published. validFrom and
        # validThrough take real dates rather than recurring ones, so emitting
        # both seasons would mean emitting one that is wrong today — and wrong
        # structured data is worse than none. The build stamps the current
        # occurrence's dates; the next rebuild rolls it over.
        from datetime import date
        today = date.today()
        spec = []
        for h in C.OUTSTANDING["hours"]:
            row = {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": f"https://schema.org/{h['day']}",
                "opens": h["open"], "closes": h["close"],
            }
            if h.get("season"):
                start, end, live = _season_window(h["season"], today)
                if not live:
                    continue
                row["validFrom"] = start.isoformat()
                row["validThrough"] = end.isoformat()
            spec.append(row)
        business["openingHoursSpecification"] = spec

    # Book Now is a real reservation entry point whether it lands on a booking
    # system or on WhatsApp, so the action is published either way and follows
    # whatever the button does. It was previously omitted entirely while
    # booking_url was empty, which meant the one action the page exists for
    # was the one thing the markup did not mention.
    business["potentialAction"] = {
        "@type": "ReserveAction",
        "target": {
            "@type": "EntryPoint",
            "urlTemplate": book_href(),
            "actionPlatform": [
                "https://schema.org/DesktopWebPlatform",
                "https://schema.org/MobileWebPlatform",
            ],
        },
        "result": {"@type": "Reservation", "name": "Nail appointment"},
    }

    maddy = {
        "@type": "Person",
        "@id": f"{C.SITE_URL}/#maddy",
        "name": b["person"],
        "jobTitle": "Nail Technician",
        "worksFor": {"@id": f"{C.SITE_URL}/#business"},
        "image": {"@id": f"{C.SITE_URL}/#portrait"},
        "url": C.SITE_URL + "/#about",
        "knowsAbout": ["Gel nails", "Builder gel", "Hard gel", "Nail art",
                       "Natural nail care"],
        "sameAs": [f"https://www.instagram.com/{b['instagram']}/"],
    }
    if C.OUTSTANDING.get("qualifications"):
        # Her own words, as given. The awarding body is deliberately absent
        # because she has not named one — see the note in config.
        maddy["hasCredential"] = {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": C.OUTSTANDING["qualifications"],
        }

    logo = {
        "@type": "ImageObject",
        "@id": f"{C.SITE_URL}/#logo",
        "url": f"{C.SITE_URL}/{LOGO}",
        "contentUrl": f"{C.SITE_URL}/{LOGO}",
        "caption": b["name"],
    }

    builder = {
        "@type": "Organization",
        "@id": f"{C.SITE_URL}/#builder",
        "name": cr["builder"],
        "url": cr["builder_url"],
        "parentOrganization": {"@id": f"{C.SITE_URL}/#builder-parent"},
    }
    parent = {
        "@type": "Organization",
        "@id": f"{C.SITE_URL}/#builder-parent",
        "name": cr["parent"],
        "url": cr["parent_url"],
    }

    website = {
        "@type": "WebSite",
        "@id": f"{C.SITE_URL}/#website",
        "url": C.SITE_URL + "/",
        "name": b["name"],
        "inLanguage": "en-GB",
        "publisher": {"@id": f"{C.SITE_URL}/#business"},
        "creator": {"@id": f"{C.SITE_URL}/#builder"},
        # No SearchAction. There is no site search to point one at, and
        # declaring one that does not exist is how you get a sitelinks
        # searchbox that 404s.
    }

    # A one-page site has no hierarchy, so this breadcrumb has exactly one
    # rung and Google will not draw it in the result. It is published because
    # it is valid, costs nothing and is already wired to the WebPage — the
    # moment there is a second page it becomes real. Do not pad it with
    # section anchors to make it look busier: fragments are not pages, and a
    # breadcrumb that lies is worse than one that is short.
    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{C.SITE_URL}/#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home",
             "item": C.SITE_URL + "/"},
        ],
    }

    webpage = {
        "@type": "WebPage",
        "@id": f"{C.SITE_URL}/#webpage",
        "url": C.SITE_URL + "/",
        "name": C.SEO["title"],
        "description": C.SEO["description"],
        "inLanguage": "en-GB",
        "isPartOf": {"@id": f"{C.SITE_URL}/#website"},
        "about": {"@id": f"{C.SITE_URL}/#business"},
        "primaryImageOfPage": {"@id": f"{C.SITE_URL}/#portrait"},
        "breadcrumb": {"@id": f"{C.SITE_URL}/#breadcrumb"},
        "datePublished": "2026-09-14",
        "dateModified": _dt.date.today().isoformat(),
    }

    faq = {
        "@type": "FAQPage",
        "@id": f"{C.SITE_URL}/#faq-schema",
        "mainEntityOfPage": {"@id": f"{C.SITE_URL}/#webpage"},
        "mainEntity": [{
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": a},
        } for q, a in C.FAQS],
    }

    graph = [business, maddy, logo, website, webpage, breadcrumb, faq,
             builder, parent] + image_objects()
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))


# ----------------------------------------------------------------------- CSS

DRAFT_CSS = """
/* ---- draft-only placeholder ---- */
.hold{border:2px dashed var(--pink);border-radius:var(--radius);
  background:repeating-linear-gradient(45deg,#fff,#fff 10px,var(--blush-2) 10px,var(--blush-2) 20px);
  padding:1.5rem;text-align:center;font-weight:600;color:var(--pink-ink);
  display:flex;flex-direction:column;align-items:center;gap:.4rem;min-height:9rem;
  justify-content:center}
.hold-tag{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;
  background:var(--pink);color:#fff;padding:.2rem .6rem;border-radius:999px}
.hold-note{font-weight:400;font-size:.85rem;color:var(--ink-60)}
"""

CSS = """
:root{
  --pink:#E8378A; --pink-ink:#B81E67; --blush:#FCE4EE; --blush-2:#FFF4F8;
  --ink:#141414; --ink-60:#5A5359; --line:#EFD9E4; --white:#fff;
  --pad:clamp(1rem,5vw,2.5rem); --max:64rem;
  --radius:18px;
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
/* The header is sticky, so an anchored section would otherwise land with its
   heading underneath it. */
/* #top is deliberately NOT in this list. It sits at the very start of the
   document, so it wants the top of the page and nothing above it; the offset
   exists for headings that would otherwise land under the sticky bar. */
section[id],#main{scroll-margin-top:4.6rem}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *{animation-duration:.01ms!important;transition-duration:.01ms!important}
}
body{
  margin:0;background:var(--white);color:var(--ink);
  font:400 clamp(1rem,.96rem + .2vw,1.075rem)/1.65 Outfit,ui-sans-serif,system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}
img,svg{max-width:100%;height:auto;display:block}
h1,h2,h3{font-family:Shrikhand,Georgia,serif;font-weight:400;line-height:1.1;
  letter-spacing:-.01em;margin:0}
a{color:var(--pink-ink)}
:focus-visible{outline:3px solid var(--pink);outline-offset:3px;border-radius:4px}

.skip{position:absolute;left:-9999px;top:0;background:var(--ink);color:#fff;
  padding:.75rem 1rem;z-index:99;border-radius:0 0 8px 0}
.skip:focus{left:0}

.wrap{max-width:var(--max);margin-inline:auto;padding-inline:var(--pad)}

/* ---- header ---- */
.site-head{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.head-in{display:flex;align-items:center;gap:.7rem;justify-content:space-between;
  padding-block:.35rem}
/* Bigger mark, SHORTER bar. The logo is mostly clear space above and below
   the wordmark, so it can grow into the padding the header was spending on
   nothing — the header ends up 6px shorter than before while the mark is
   half again as wide. A sticky header costs the same height on every screen,
   which on a phone is the scarcest thing there is. */
.logo{width:clamp(150px,40vw,190px);height:auto;display:block}
/* min-height, not more padding. Measured at 390px the header button came
   out 43.2px — eight tenths of a pixel under the 44px target size, which
   is the sort of miss no eye catches and every thumb does. Padding alone
   was the wrong lever: it would have grown the sticky bar on every screen
   to fix a shortfall on one. */
.head-in .btn{padding:.5rem .95rem;font-size:.88rem;min-height:44px}
.head-right{display:flex;align-items:center;gap:.6rem}

/* ---- section nav, no JavaScript ----
   A checkbox and its label. The CSP forbids scripts, and a burger is one
   boolean — there is nothing here JavaScript would do better. The page is
   long on a phone (nineteen photographs, twenty prices, six FAQs), so the
   nav is not decoration: it is the difference between scrolling past the
   prices and going to them. */
.burger{display:none;width:44px;height:44px;border-radius:12px;cursor:pointer;
  align-items:center;justify-content:center;border:1px solid var(--line);
  background:#fff;flex:0 0 auto}
.burger span,.burger span::before,.burger span::after{display:block;
  width:18px;height:2px;background:var(--ink);border-radius:2px;content:""}
.burger span{position:relative}
.burger span::before{position:absolute;top:-6px}
.burger span::after{position:absolute;top:6px}
.burger:focus-visible{outline:3px solid var(--pink);outline-offset:2px}
.nav-close{display:none}
.nav{border-top:1px solid var(--line);background:#fff}
.nav .wrap{display:flex;gap:1.4rem;overflow-x:auto;padding-block:.6rem;
  scrollbar-width:none}
.nav .wrap::-webkit-scrollbar{display:none}
.nav a{font-family:Outfit,sans-serif;font-weight:600;font-size:.82rem;
  letter-spacing:.06em;text-transform:uppercase;color:var(--ink);
  text-decoration:none;white-space:nowrap;padding:.35rem 0;
  border-bottom:2px solid transparent}
.nav a:hover,.nav a:focus-visible{border-bottom-color:var(--pink)}

@media (max-width:43.99rem){
  .burger{display:flex}
  /* Closed by default on a phone; the URL fragment is the whole mechanism. */
  .nav{display:none}
  .nav:target{display:block}
  .nav-close{display:block;color:var(--ink-60)}
  .nav .wrap{flex-direction:column;gap:0;overflow:visible;padding-block:.2rem}
  .nav a{padding:.85rem .1rem;border-bottom:1px solid var(--line);
    border-top:none;font-size:.9rem}
  .nav a:last-child{border-bottom:none}
  .nav a:hover,.nav a:focus-visible{border-bottom-color:var(--line);
    color:var(--pink-ink)}
}

/* ---- back to top ----
   Always present rather than appearing on scroll, because appearing on
   scroll needs a scroll listener and there is no JavaScript. Small, low
   contrast, out of the thumb's way at the bottom-right. */
.totop{position:fixed;right:.9rem;bottom:.9rem;z-index:30;
  width:44px;height:44px;border-radius:50%;display:flex;
  align-items:center;justify-content:center;text-decoration:none;
  background:rgba(20,20,22,.55);color:#fff;font-size:1.1rem;line-height:1;
  backdrop-filter:blur(6px)}
.totop:hover,.totop:focus-visible{background:var(--pink)}
@media print{.totop,.burger,.nav{display:none}}

/* ---- buttons ---- */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;
  background:var(--pink);color:#fff;text-decoration:none;font-weight:600;
  padding:.85rem 1.4rem;border-radius:999px;border:2px solid var(--pink);
  transition:background .15s ease,border-color .15s ease,transform .15s ease;
  text-align:center}
.btn:hover{background:var(--pink-ink);border-color:var(--pink-ink)}
.btn:active{transform:translateY(1px)}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--ink)}
.btn.ghost:hover{background:var(--ink);color:#fff}
.btn .ico{width:18px;height:18px;flex:none}
@media (max-width:26rem){.cta .btn{flex:1 1 100%}}
.head-in .btn .ico{width:16px;height:16px}

/* ---- hero ---- */
.hero{background:linear-gradient(180deg,var(--blush) 0%,var(--blush-2) 70%,#fff 100%);
  padding-block:clamp(2.5rem,8vw,5rem) clamp(2rem,6vw,3.5rem);text-align:center}
.eyebrow{margin:0 0 .9rem;font-size:.82rem;font-weight:600;letter-spacing:.11em;
  text-transform:uppercase;color:var(--pink-ink)}
.hero h1{font-size:clamp(2rem,1.3rem + 3.6vw,3.4rem);max-width:15ch;margin-inline:auto}
.lead{max-width:46ch;margin:1.1rem auto 0;color:var(--ink-60);font-size:1.075em}
.cta{display:flex;flex-wrap:wrap;gap:.75rem;justify-content:center;margin-top:1.9rem}

/* ---- trust strip ---- */
.strip{background:var(--ink);color:#fff}
.strip ul{display:flex;flex-wrap:wrap;justify-content:center;gap:.5rem 2rem;
  margin:0;padding:.9rem 0;list-style:none;font-size:.86rem;font-weight:500;
  letter-spacing:.02em}
.strip li::before{content:"✦";color:var(--pink);margin-right:.5rem}

/* ---- sections ---- */
section{padding-block:clamp(2.5rem,7vw,4.5rem)}
.tint{background:var(--blush-2)}
h2{font-size:clamp(1.6rem,1.2rem + 2vw,2.35rem);margin-bottom:1.4rem}
.note{color:var(--ink-60);font-size:.85rem;margin-top:1.2rem}

/* ---- about ---- */
.about{display:grid;gap:1.6rem}
.about-copy p{margin:0 0 1rem}
.about-copy p:last-child{margin-bottom:0}
.portrait img{border-radius:var(--radius);width:100%;object-fit:cover;aspect-ratio:4/5}
.quals{font-size:.92rem;color:var(--ink-60)}
@media (min-width:44rem){
  .about{grid-template-columns:minmax(0,18rem) 1fr;align-items:start;gap:2.5rem}
}

/* ---- prices ---- */
.grp{font-family:Outfit,sans-serif;font-weight:700;font-size:.82rem;
  letter-spacing:.11em;text-transform:uppercase;color:var(--pink-ink);
  margin:2rem 0 .6rem}
.grp:first-of-type{margin-top:0}
/* One line under each heading. Tight to it, so it reads as part of the
   heading rather than as the first item in the list. */
.grp-note{margin:0 0 .85rem;color:var(--ink-60);font-size:.94rem;
  line-height:1.5;max-width:54ch}
.prices,.hours{margin:0}

/* ---- what she uses ---- */
.products{margin-top:2.4rem;padding-top:1.6rem;border-top:1px solid var(--line)}
.products h3{font-family:Outfit,sans-serif;font-weight:700;font-size:.82rem;
  letter-spacing:.11em;text-transform:uppercase;color:var(--pink-ink);
  margin:0 0 .7rem}
.products p{margin:0 0 .9rem;color:var(--ink-60);line-height:1.6;max-width:62ch}
/* The HEMA line is set apart on purpose: it is the sentence that decides
   whether someone who has reacted to gel before feels able to book at all.
   Buried in a paragraph it is a detail; in its own block it is an answer. */
.products .hema{background:var(--blush);border-left:3px solid var(--pink);
  border-radius:0 10px 10px 0;padding:.9rem 1.1rem;margin:0 0 .9rem;
  color:var(--ink);font-weight:600}
.products .aside{font-size:.9rem;margin-bottom:0}
/* Supplier marks. A plain row on white cards — no border, no "partner" or
   "approved" framing, because none is claimed. */
.suppliers{list-style:none;margin:0 0 1rem;padding:0;display:flex;
  flex-wrap:wrap;gap:.6rem}
.suppliers li{flex:0 1 auto}
/* Transparent background on the supplier marks — APPROVED BY ANDY, 26 Sep,
   which is why this is here at all. AGENTS.md item 8 forbids recolouring these
   marks and the Controls preamble says to ask rather than work around; this is
   the answer to that ask, recorded so the next reader sees the permission and
   not just the code.
   Both files are RGB with baked-in white and no alpha, so the white was not
   decoration. Keying it out is doubly wrong: it is the file, and the American
   Creator flag's stars and stripes ARE white, so a key punches holes through
   the mark. `multiply` is a rendering choice instead — the published bytes stay
   identical and verify.py still compares them.
   Measured in Chromium at 390px, not assumed: every mark corner lands on this
   section's #FFF4F8 exactly (0 of 8 white, against 1-2 of 4 before). It does
   also multiply the ink, by a mean of 7.6/255 across 95% of the mark's pixels,
   worst 16 — about 3%, and the number Andy was given before approving.
   The permanent fix is transparent PNG or SVG from the two suppliers; ask for
   them and this rule can go. */
.suppliers img{display:block;width:auto;height:52px;background:#fff}
@supports (mix-blend-mode:multiply){
  .suppliers img{background:transparent;mix-blend-mode:multiply}
}
/* Season label left, time right, so a seasonal day's hours land in the same
   column as every other day's. With the label trailing, Thursday read as a
   different table from the rest. */
.hours .season{font-weight:400;color:var(--ink-60);font-size:.84em;
  white-space:nowrap;margin-right:.55rem}
.hours .hrs{font-variant-numeric:tabular-nums;white-space:nowrap}
.hours dd{display:flex;flex-direction:column;gap:.2rem;align-items:flex-end}
.hours .win{display:inline-flex;align-items:baseline;justify-content:flex-end}
.row{display:flex;align-items:baseline;gap:.6rem;padding:.6rem 0;
  border-bottom:1px solid var(--line)}
.row dt{flex:1;margin:0;font-weight:500}
.row dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.dur{display:block;font-size:.8rem;font-weight:400;color:var(--ink-60)}

/* ---- reviews ---- */
.quotes{display:grid;gap:1rem}
.quote{margin:0;background:#fff;border:1px solid var(--line);border-radius:var(--radius);
  padding:1.4rem 1.5rem}
.quote p{margin:0;font-size:1.05em}
.quote p::before{content:"“"}
.quote p::after{content:"”"}
.quote cite{display:block;margin-top:.8rem;font-style:normal;font-weight:600;font-size:.88rem}
.quote cite span{font-weight:400;color:var(--ink-60)}
@media (min-width:52rem){.quotes{grid-template-columns:repeat(3,1fr)}}

/* ---- gallery ---- */
/* Three across on a phone, not two. Nineteen photographs two-up is most of
   the page's length on its own, and at this size the set is still legible —
   the detail panel is where anyone looks properly anyway. */
.grid{display:grid;gap:.45rem;grid-template-columns:repeat(3,1fr)}
.grid .tile{margin:0}
/* tiles link to the post when the gallery comes from Instagram */
.grid .tile a{display:block;border-radius:12px;overflow:hidden}
.grid img{border-radius:12px;aspect-ratio:1;object-fit:cover;width:100%;display:block}
@media (min-width:44rem){.grid{grid-template-columns:repeat(3,1fr);gap:1rem}}

/* tiles are links into the :target panels below */
.grid .tile a{position:relative;display:block;border-radius:12px;overflow:hidden}
.grid .tile a:focus-visible{outline:3px solid var(--pink);outline-offset:3px}
.grid .badge{position:absolute;top:.5rem;left:.5rem;z-index:1;
  font-size:.7rem;font-weight:700;letter-spacing:.04em;line-height:1;
  padding:.32rem .45rem;border-radius:6px;color:#fff;
  background:rgba(20,20,22,.62)}
/* Level 3 is the gold standard, so it is the one that gets gold. */
.grid .badge.b3{background:linear-gradient(135deg,#a8842c,#d9b355);color:#1a1405}
.grid .more{position:absolute;right:.5rem;bottom:.5rem;z-index:1;
  width:26px;height:26px;border-radius:50%;background:rgba(20,20,22,.62);
  color:#fff;font-size:1rem;line-height:26px;text-align:center;font-weight:600}
.grid-hint{margin:.9rem 0 0;font-size:.9rem;color:var(--ink-60)}

/* ---- set detail (:target, no JavaScript — CSP sets script-src 'none') ---- */
.lb{display:none}
.lb:target{display:flex;position:fixed;inset:0;z-index:50;
  align-items:center;justify-content:center;padding:1rem}
/* full-bleed anchor behind the card: tapping the backdrop closes it */
.lb-back{position:absolute;inset:0;background:rgba(20,20,22,.78)}
.lb-card{position:relative;z-index:1;background:var(--paper,#fff);
  border-radius:16px;overflow:auto;max-width:34rem;max-height:92vh;
  box-shadow:0 18px 50px rgba(0,0,0,.35)}
.lb-card img{display:block;width:100%;height:auto;aspect-ratio:1;object-fit:cover}
.lb-copy{padding:1.1rem 1.2rem 1.3rem}
.lvl{margin:0 0 .7rem;font-size:.92rem;line-height:1.45}
.lvl b{display:block;font-size:1rem}
.lvl span{color:var(--ink-60)}
.lvl em{display:block;font-style:normal;font-weight:600;margin-top:.2rem}
.lvl-3 b{color:#8a6a1e}
.lb-note{margin:0 0 1rem;color:var(--ink-60);line-height:1.6}
.lb-x{display:inline-block;min-height:44px;line-height:44px;padding:0 1.3rem;
  border-radius:999px;background:var(--pink);color:#fff;font-weight:600;
  text-decoration:none}
@media (min-width:44rem){
  .lb-card{max-width:52rem;display:grid;grid-template-columns:1fr 1fr}
  .lb-card img{height:100%}
  .lb-copy{align-self:center}
}

/* ---- find ---- */
.find{display:grid;gap:1.5rem}
.addr{font-style:normal;font-size:1.1em;line-height:1.5;margin:0 0 1rem}
/* Her name is the bold line. The salon is where she works from, not who
   the client is booking. */
.addr b{display:block;font-weight:700;font-size:1.12em}
.addr .venue{display:block;color:var(--ink-60);font-size:.9em;
  margin:.1rem 0 .35rem}
.addr-note{color:var(--ink-60);font-size:.9rem}
.hours .row dd{font-weight:600}
@media (min-width:44rem){.find{grid-template-columns:1fr 1fr;gap:2.5rem}}

/* ---- faq ---- */
.faqs{border-top:1px solid var(--line)}
.faq{border-bottom:1px solid var(--line)}
.faq summary{cursor:pointer;list-style:none;padding:1rem 2rem 1rem 0;
  font-weight:600;position:relative}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"";position:absolute;right:.4rem;top:1.45rem;
  width:9px;height:9px;border-right:2px solid var(--pink);
  border-bottom:2px solid var(--pink);transform:rotate(45deg);
  transition:transform .18s ease}
.faq[open] summary::after{transform:rotate(-135deg);top:1.7rem}
.faq p{margin:0 0 1.1rem;color:var(--ink-60);max-width:62ch}

/* ---- footer ---- */
.site-foot{background:var(--ink);color:#fff;padding-block:2.5rem;font-size:.9rem}
.site-foot a{color:#fff}
.site-foot .logo{width:120px;margin-bottom:1.2rem}
.foot-rows{display:grid;gap:.35rem}
.fine{margin-top:1.4rem;color:#9C9298;font-size:.8rem}

"""

FONT_FACES = """
@font-face{font-family:Outfit;src:url(fonts/outfit-latin-400-normal.woff2)format('woff2');
  font-weight:400;font-display:swap;font-style:normal}
@font-face{font-family:Outfit;src:url(fonts/outfit-latin-500-normal.woff2)format('woff2');
  font-weight:500;font-display:swap;font-style:normal}
@font-face{font-family:Outfit;src:url(fonts/outfit-latin-600-normal.woff2)format('woff2');
  font-weight:600;font-display:swap;font-style:normal}
@font-face{font-family:Outfit;src:url(fonts/outfit-latin-700-normal.woff2)format('woff2');
  font-weight:700;font-display:swap;font-style:normal}
@font-face{font-family:Shrikhand;src:url(fonts/shrikhand-latin-400-normal.woff2)format('woff2');
  font-weight:400;font-display:swap;font-style:normal}
"""


# ---------------------------------------------------------------------- page

def build():
    PUB.mkdir(parents=True, exist_ok=True)
    copy_assets()
    b, o, cr = C.BUSINESS, C.OUTSTANDING, C.CREDIT

    # DRAFT no longer paints a banner across the top. It still does the work
    # that matters — noindex, placeholders for missing content, and hiding
    # reviews nobody has agreed to publish — but the visible label is gone.
    # A banner saying "not live" on a site people are being shown is a note
    # to ourselves in the client's line of sight.
    #
    # Which means the ONLY remaining signal that this is a draft is the
    # noindex tag. Check config.DRAFT before assuming the site is live.
    from PIL import Image as _Im
    share_w, share_h = _Im.open(PUB / SHARE).size

    ribbon = ""
    robots = '<meta name="robots" content="noindex,nofollow">' if C.DRAFT else ""

    trust = "".join(f"<li>{esc(t)}</li>" for t in C.TRUST)
    maps_link = (f'<p><a href="{esc(b["maps"])}" rel="noopener">Open in Google Maps</a></p>')

    page = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(C.SEO["title"])}</title>
<meta name="description" content="{H.escape(C.SEO["description"])}">
<link rel="canonical" href="{C.SITE_URL}/">
{robots}
<meta name="theme-color" content="#E8378A">
<meta property="og:type" content="website">
<meta property="og:locale" content="en_GB">
<meta property="og:site_name" content="{esc(b["name"])}">
<meta property="og:title" content="{esc(C.SEO["title"])}">
<meta property="og:description" content="{H.escape(C.SEO["description"])}">
<meta property="og:url" content="{C.SITE_URL}/">
<meta property="og:image" content="{C.SITE_URL}/{SHARE}">
<meta property="og:image:alt" content="{H.escape(b["name"])} — {H.escape(b["tagline"])}, {esc(b["town"])}">
<meta property="og:image:width" content="{share_w}">
<meta property="og:image:height" content="{share_h}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image:alt" content="{H.escape(b["name"])} — {H.escape(b["tagline"])}, {esc(b["town"])}">
<link rel="icon" href="favicon.png" sizes="32x32">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preload" href="fonts/outfit-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/shrikhand-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<style>{FONT_FACES}{CSS}{DRAFT_CSS if C.DRAFT else ""}</style>
<script type="application/ld+json">{schema()}</script>
</head>
<body>
<!-- The back-to-top anchor. It has to be its own empty element, NOT the
     header: the header is position:sticky, and a stuck element never leaves
     the viewport, so the browser had nothing to scroll and href="#top" did
     precisely nothing at any scroll position. Reported as "the return to top
     arrow doesn't work", and it never had. The brand mark and the nav's Close
     link point at #top too, so all three were affected. -->
<span id="top"></span>
<a class="skip" href="#main">Skip to content</a>
{ribbon}

<header class="site-head">
  <div class="wrap head-in">
    <a class="brand" href="#top" aria-label="Nails by Maddy — home">{logo_img()}</a>
    <div class="head-right">
      {cta()}
      <a class="burger" href="#menu" aria-label="Open menu"><span></span></a>
    </div>
  </div>
  <!-- :target, not a checkbox. A checkbox stays checked, so after tapping
       "Find me" the menu was still open and sitting on top of the section it
       had just jumped to. With :target, following any section link moves the
       target off #menu and the menu closes itself — the same click that
       navigates also tidies up. No JavaScript either way. -->
  <nav class="nav" id="menu" aria-label="Sections">
    <div class="wrap">
      <a href="#about">About</a>
      <a href="#prices">Prices</a>
      <a href="#work">Gallery</a>
      <a href="#reviews">Reviews</a>
      <a href="#faq">FAQs</a>
      <a href="#find">Find me</a>
      <a class="nav-close" href="#top">Close</a>
    </div>
  </nav>
</header>

<main id="main">

  <div class="hero">
    <div class="wrap">
      <p class="eyebrow">{esc(C.HERO["eyebrow"])}</p>
      <h1>{esc(C.HERO["h1"])}</h1>
      <p class="lead">{esc(C.HERO["lead"])}</p>
      {cta_row()}
    </div>
  </div>

  <div class="strip"><div class="wrap"><ul>{trust}</ul></div></div>

  <section id="about">
    <div class="wrap">
      <h2>Hello, I'm Maddy</h2>
      {about_html()}
    </div>
  </section>

  <section id="prices" class="tint">
    <div class="wrap">
      <h2>Treatments &amp; prices</h2>
      {price_html()}
      <p class="note">Prices from the live booking menu, September 2026.
         Nail art is added to any treatment.</p>
    </div>
  </section>

  <section id="reviews">
    <div class="wrap">
      <h2>What clients say</h2>
      {reviews_html()}
    </div>
  </section>

  <section id="faq" class="tint">
    <div class="wrap">
      <h2>Questions people ask</h2>
      {faq_html()}
    </div>
  </section>

  <section id="work">
    <div class="wrap">
      <h2>Recent sets</h2>
      {gallery_html()}
    </div>
  </section>

  <section id="find" class="tint">
    <div class="wrap">
      <h2>Find me</h2>
      <div class="find">
        <div>
          <address class="addr"><b>{esc(b["name"])}</b><span class="venue">{esc(b["venue_note"])}</span>{esc(b["street"])}<br>
            {esc(b["town"])}<br>{esc(b["postcode"])}</address>
          {maps_link}
          {cta_row("left")}
        </div>
        <div>{hours_html()}</div>
      </div>
    </div>
  </section>

</main>

<a class="totop" href="#top" aria-label="Back to top">↑</a>

<footer class="site-foot">
  <div class="wrap">
    {logo_img(LOGO_WHITE)}
    <div class="foot-rows">
      <div><a href="tel:{b["phone_e164"]}">{esc(b["phone"])}</a></div>
      <div><a href="mailto:{esc(b["email"])}">{esc(b["email"])}</a></div>
      <div><a href="https://www.instagram.com/{esc(b["instagram"])}/" rel="me noopener">
        @{esc(b["instagram"])}</a></div>
      <div>{esc(b["venue"])}, {esc(b["street"])}, {esc(b["town"])} {esc(b["postcode"])}</div>
    </div>
    <p class="fine">&copy; {_dt.date.today().year} {esc(b["name"])}. Site by
      <a href="{esc(cr["builder_url"])}" rel="noopener">{esc(cr["builder"])}</a>,
      part of the
      <a href="{esc(cr["parent_url"])}" rel="noopener">{esc(cr["parent"])}</a>.</p>
  </div>
</footer>
</body>
</html>
"""
    (PUB / "index.html").write_text(page, encoding="utf-8")

    # Small, self-contained, same styling — no fonts needed for four lines.
    (PUB / "404.html").write_text(f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page not found — {esc(b["name"])}</title>
<meta name="robots" content="noindex">
<link rel="icon" href="/favicon.png" sizes="32x32">
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;
text-align:center;padding:2rem;background:#FCE4EE;color:#141414;
font:400 1rem/1.6 ui-sans-serif,system-ui,sans-serif}}
h1{{font-size:1.6rem;margin:0 0 .5rem}}
a{{color:#B81E67;font-weight:600}}</style></head>
<body><main><img src="/{LOGO}" alt="{esc(b["name"])}" width="200" height="93"
 style="margin:0 auto 1.5rem">
<h1>That page isn't here</h1>
<p>Try the <a href="/">home page</a>, or ring Maddy on
<a href="tel:{b["phone_e164"]}">{esc(b["phone"])}</a>.</p>
</main></body></html>
""", encoding="utf-8")

    (PUB / "robots.txt").write_text(
        ("User-agent: *\nDisallow: /\n" if C.DRAFT else
         f"User-agent: *\nAllow: /\n\nSitemap: {C.SITE_URL}/sitemap.xml\n"),
        encoding="utf-8")

    # Sitemap. One URL, because there is one page — and twenty images, which
    # is the part that earns its keep. The image extension is how Google
    # Images is told these photographs exist and what each one is; without it
    # a crawler has a filename and an alt attribute and nothing else.
    #
    # changefreq and priority are deliberately absent. Google has said for
    # years that it ignores both, and a sitemap carrying fields nobody reads
    # is a sitemap whose accurate fields are harder to trust. lastmod is the
    # one hint Google does use, so it is the one that is here.
    # image:title and image:caption are NOT emitted. Google deprecated
    # image:caption, image:geo_location, image:title and image:license on
    # 25 May 2022 and stopped reading them that August; <image:loc> is the
    # only child element the current spec still defines. Sending the rest is
    # not harmful, it is just noise in a file whose whole job is to be
    # trusted — and it invites the belief that the caption is doing work.
    # What each photograph IS gets said in the alt attribute and in the
    # ImageObject entities in the @graph, both of which Google does read.
    def _img_entry(url):
        return (f"      <image:image>\n"
                f"        <image:loc>{H.escape(url, quote=False)}</image:loc>\n"
                f"      </image:image>")

    entries = [_img_entry(f"{C.SITE_URL}/{img(x['file'])}") for x in o["gallery"]]
    pt = o.get("portrait")
    if pt:
        entries.insert(0, _img_entry(f"{C.SITE_URL}/{img(pt['file'])}"))
    entries.insert(0, _img_entry(f"{C.SITE_URL}/{SHARE}"))

    (PUB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        '  <url>\n'
        f'    <loc>{C.SITE_URL}/</loc>\n'
        f'    <lastmod>{_dt.date.today().isoformat()}</lastmod>\n'
        + "\n".join(entries) + "\n"
        '  </url>\n'
        '</urlset>\n', encoding="utf-8")


    # ---- _headers and _redirects are deliberately NOT generated ----------
    # They used to be, for the abandoned Pages Direct Upload path, on the
    # assumption they were "harmless on the Worker path". They are not.
    # Workers Assets rejects an absolute URL in _redirects outright:
    #
    #   ✘ Invalid _redirects configuration:
    #     Line 1: Only relative URLs are allowed. [code: 100324]
    #
    # and the www → apex rule has to be absolute, because the whole point is
    # to move between hosts. Pages allowed it; Workers does not. That one line
    # failed every deploy while the build itself passed every check — the
    # error arrives from the API after the upload, so the log looks healthy
    # right up to the last line.
    #
    # Nothing is lost by dropping them: worker.js sets the same security
    # headers, the same cache rules and the same 301 in code, which is the
    # single source of truth. Anything re-adding these files will break the
    # deploy again.
    for stale in ("_headers", "_redirects"):
        (PUB / stale).unlink(missing_ok=True)

    kb = (PUB / "index.html").stat().st_size / 1024
    print(f"built public/index.html — {kb:.0f} KB  ·  draft={C.DRAFT}")
    left = [k for k, v in o.items() if not v]
    print("outstanding:", ", ".join(left) if left else "nothing — ready to launch")


if __name__ == "__main__":
    build()
