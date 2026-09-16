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
PUB = ROOT / "public"                    # generated — never edit, never committed
NODE = ROOT / "node_modules/@fontsource"

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


def hours_html():
    hrs = C.OUTSTANDING["hours"]
    if not hrs:
        return (hold("Opening hours", "her days and times at Kizuri")
                or '<p class="addr-note">Ring or message to book an appointment.</p>')
    rows = "".join(
        f'<div class="row"><dt>{esc(h["day"])}</dt><dd>{esc(h["open"])}–{esc(h["close"])}</dd></div>'
        for h in hrs
    )
    return f'<dl class="hours">{rows}</dl>'


def gallery_html():
    g = C.OUTSTANDING["gallery"]
    if not g:
        return hold("Photographs of recent sets", "15–20 of her best, plus a portrait")
    tiles = "".join(
        f'<figure class="tile"><img src="img/{esc(x["file"])}" alt="{H.escape(x["alt"])}" '
        f'loading="lazy" decoding="async" width="600" height="600"></figure>' for x in g
    )
    return f'<div class="grid">{tiles}</div>'


def about_html():
    p = C.OUTSTANDING["portrait"]
    body = "".join(f"<p>{esc(t)}</p>" for t in C.ABOUT)
    q = C.OUTSTANDING["qualifications"]
    if q:
        body += f'<p class="quals">{esc(q)}</p>'
    else:
        body += hold("Qualifications and insurer", "for the about section")

    if p:
        pic = (f'<figure class="portrait"><img src="img/{esc(p["file"])}" '
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
        d["openingHoursSpecification"] = [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": f"https://schema.org/{h['day']}",
            "opens": h["open"], "closes": h["close"],
        } for h in C.OUTSTANDING["hours"]]
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
.grid img{border-radius:12px;aspect-ratio:1;object-fit:cover;width:100%}
@media (min-width:44rem){.grid{grid-template-columns:repeat(3,1fr);gap:1rem}}

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


    # ---- for the no-CLI path -------------------------------------------
    # Dragging public/ into the Cloudflare dashboard deploys the files but not
    # worker.js, so the headers and the www redirect would be lost. Cloudflare
    # reads these two plain-text files instead, which recovers both without
    # anyone needing a terminal. Harmless on the Worker path, which supports
    # the same files.
    (PUB / "_headers").write_text("""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  Content-Security-Policy: default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'

/fonts/*
  Cache-Control: public, max-age=31536000, immutable

/img/*
  Cache-Control: public, max-age=31536000, immutable

/*.html
  Cache-Control: public, max-age=0, must-revalidate
""", encoding="utf-8")

    (PUB / "_redirects").write_text(
        f"https://www.{C.DOMAIN}/* https://{C.DOMAIN}/:splat 301\n", encoding="utf-8")

    kb = (PUB / "index.html").stat().st_size / 1024
    print(f"built public/index.html — {kb:.0f} KB  ·  draft={C.DRAFT}")
    left = [k for k, v in o.items() if not v]
    print("outstanding:", ", ".join(left) if left else "nothing — ready to launch")


if __name__ == "__main__":
    build()
