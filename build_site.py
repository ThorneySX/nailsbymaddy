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
        ("nailsbymaddy-logo-primary.svg", "img/logo.svg"),
        ("nailsbymaddy-logo-reversed.svg", "img/logo-reversed.svg"),
        ("nailsbymaddy-icon-32.png", "favicon.png"),
        ("nailsbymaddy-icon-180.png", "apple-touch-icon.png"),
        ("nailsbymaddy-icon-512.png", "img/icon-512.png"),
        ("nailsbymaddy-profile-badge.png", "img/share.png"),
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


def logo_img(file="img/logo.svg", cls="logo", eager=True):
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
    for group, items in C.GROUPS:
        rows = "".join(
            f'<div class="row"><dt>{esc(label)}'
            f'<span class="dur">{esc(sv[key]["dur"])}</span></dt>'
            f'<dd>{esc(sv[key]["price"].replace(".00", ""))}</dd></div>'
            for key, label in items
        )
        out.append(f'<h3 class="grp">{esc(group)}</h3><dl class="prices">{rows}</dl>')
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


def actions():
    """
    Book online / WhatsApp / Call, in that order — but only the ones that exist,
    and whichever is first becomes the primary button.

    Order is deliberate. Booking online is the least friction and works at
    midnight, so it leads whenever there is a system to point at. Until then
    WhatsApp leads: most people would rather message a nail tech than ring one,
    and it leaves her a written record of what they asked for. Calling comes
    last but never goes away — it is the only one that works for someone who
    doesn't use WhatsApp.
    """
    b, o = C.BUSINESS, C.OUTSTANDING
    out = []

    if o["booking_url"]:
        out.append(("book", esc(o["booking_url"]), "Book online", "Book an appointment online"))

    if b.get("whatsapp"):
        from urllib.parse import quote
        href = f'https://wa.me/{b["whatsapp"]}?text={quote(b["whatsapp_msg"])}'
        out.append(("whatsapp", href, "WhatsApp", "Message Maddy on WhatsApp"))

    out.append(("call", f'tel:{b["phone_e164"]}', "Call", f'Ring Maddy on {b["phone"]}'))
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
    note = ""
    if C.DRAFT and not C.OUTSTANDING["booking_url"]:
        note = ('<p class="addr-note">Draft note: <b>Book online</b> appears here once '
                'the booking system is chosen. WhatsApp and Call work now.</p>')
    return f'<div class="cta"{style}>{html_}</div>{note}'


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
            t = f'{esc(h["open"])}–{esc(h["close"])}'
            if h.get("season"):
                t += f' <span class="season">{esc(C.SEASONS[h["season"]]["label"])}</span>'
            parts.append(t)
        rows.append(f'<div class="row"><dt>{esc(day)}</dt>'
                    f'<dd>{"<br>".join(parts)}</dd></div>')
    return f'<dl class="hours">{"".join(rows)}</dl>'


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
    out = []
    for r in C.REVIEWS:
        if C.DRAFT or r["public"]:
            out.append(
                f'<blockquote class="quote"><p>{esc(r["text"])}</p>'
                f'<cite>{esc(r["who"])} <span>· {esc(r["src"])}</span></cite></blockquote>'
            )
    note = hold("Permission to publish", "confirm with each client first") if C.DRAFT else ""
    return f'<div class="quotes">{"".join(out)}</div>{note}'


# ------------------------------------------------------------------ metadata

def schema():
    """
    NailSalon, not LocalBusiness — the more specific type wins.
    No aggregateRating: one review isn't a rating, and self-serving review
    markup breaks Google's guidelines.
    """
    b = C.BUSINESS
    sv = services()
    offers = []
    for group, items in C.GROUPS:
        for key, label in items:
            s = sv[key]
            offers.append({
                "@type": "Offer",
                "itemOffered": {"@type": "Service", "name": label, "category": group},
                "price": s["price"].replace("£", "").replace(".00", ""),
                "priceCurrency": "GBP",
            })

    d = {
        "@context": "https://schema.org",
        "@type": "NailSalon",
        "@id": f"{C.SITE_URL}/#business",
        "name": b["name"],
        "url": C.SITE_URL + "/",
        "telephone": b["phone_e164"],
        "email": b["email"],
        "image": f"{C.SITE_URL}/img/share.png",
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
        "areaServed": [{"@type": "City", "name": n}
                       for n in ("Westcliff-on-Sea", "Southend-on-Sea", "Leigh-on-Sea", "Chalkwell")],
        "sameAs": [f"https://www.instagram.com/{b['instagram']}/", b["maps"]],
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
        d["openingHoursSpecification"] = spec
    if C.OUTSTANDING["booking_url"]:
        d["potentialAction"] = {
            "@type": "ReserveAction",
            "target": {"@type": "EntryPoint", "urlTemplate": C.OUTSTANDING["booking_url"]},
        }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": a},
        } for q, a in C.FAQS],
    }
    # Two graphs in one script — valid, and keeps the head tidy.
    return json.dumps([d, faq], ensure_ascii=False, separators=(",", ":"))


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
.ribbon{background:var(--ink);color:#fff;text-align:center;padding:.6rem 1rem;
  font-size:.82rem;font-weight:600;letter-spacing:.04em}
.ribbon b{color:var(--pink)}
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
.head-in{display:flex;align-items:center;gap:1rem;justify-content:space-between;
  padding-block:.7rem}
.logo{width:clamp(108px,26vw,140px);height:auto}
.head-in .btn{padding:.55rem 1rem;font-size:.9rem}

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
.prices,.hours{margin:0}
.hours .season{font-weight:400;color:var(--muted);font-size:.86em;white-space:nowrap}
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
.grid{display:grid;gap:.7rem;grid-template-columns:repeat(2,1fr)}
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
.addr b{display:block;font-weight:700}
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
    b, o = C.BUSINESS, C.OUTSTANDING

    ribbon = ('<div class="ribbon">Draft — <b>not live</b>. Dashed blocks are '
              'waiting on Maddy.</div>') if C.DRAFT else ""
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
<meta property="og:image" content="{C.SITE_URL}/img/share.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="favicon.png" sizes="32x32">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preload" href="fonts/outfit-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/shrikhand-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<style>{FONT_FACES}{CSS}{DRAFT_CSS if C.DRAFT else ""}</style>
<script type="application/ld+json">{schema()}</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{ribbon}

<header class="site-head">
  <div class="wrap head-in">
    <a href="#main" aria-label="Nails by Maddy — home">{logo_img()}</a>
    {cta()}
  </div>
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
          <address class="addr"><b>{esc(b["venue"])}</b>{esc(b["street"])}<br>
            {esc(b["town"])}<br>{esc(b["postcode"])}</address>
          {maps_link}
          {cta_row("left")}
        </div>
        <div>{hours_html()}</div>
      </div>
    </div>
  </section>

</main>

<footer class="site-foot">
  <div class="wrap">
    {logo_img("img/logo-reversed.svg")}
    <div class="foot-rows">
      <div><a href="tel:{b["phone_e164"]}">{esc(b["phone"])}</a></div>
      <div><a href="mailto:{esc(b["email"])}">{esc(b["email"])}</a></div>
      <div><a href="https://www.instagram.com/{esc(b["instagram"])}/" rel="me noopener">
        @{esc(b["instagram"])}</a></div>
      <div>{esc(b["venue"])}, {esc(b["street"])}, {esc(b["town"])} {esc(b["postcode"])}</div>
    </div>
    <p class="fine">&copy; 2026 {esc(b["name"])}. Site by
      <a href="https://wincustomers.co.uk/" rel="noopener">WinCustomers</a>.</p>
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
<body><main><img src="/img/logo.svg" alt="{esc(b["name"])}" width="200" height="93"
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

    (PUB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{C.SITE_URL}/</loc><changefreq>monthly</changefreq>'
        f'<priority>1.0</priority></url>\n</urlset>\n', encoding="utf-8")


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
