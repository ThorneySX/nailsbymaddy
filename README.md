# nailsbymaddy.co.uk

One page, static, served from a Cloudflare Worker. No framework, no JavaScript
on the page, no third-party requests — fonts, logos and every photograph are
self-hosted, which is why the CSP can be `default-src 'self'; script-src 'none'`.

52 KB of HTML, about 11 KB over the wire. No layout shift; every image is
dimensioned.

> **Changing anything? Read [`AGENTS.md`](AGENTS.md) first.** This file explains
> how the site works; that one lists the invariants — brand rules that were
> broken once, legal constraints on prices and supplier marks, and the
> thresholds that go stale silently. It is short.

---

## Deploying — no terminal needed

This repo is connected to a Cloudflare Worker through **Workers Builds**.
Cloudflare runs the build on their machines, so nothing needs installing
anywhere. **Push to `main` and the site deploys.** Edit a file on github.com in
a browser and that counts as a push.

Settings on the Cloudflare side, under the Worker → Settings → Builds:

| Field | Value |
|---|---|
| Build command | `npm ci --include=dev && npm run ci` |
| Deploy command | `npx wrangler deploy` |
| Root directory | `/` |
| Production branch | `main` |

`npm run ci` is `npm run deps` → `build_site.py` → `verify.py --no-browser`. A
failing check exits non-zero, Cloudflare stops, and **nothing deploys**.

### Python dependencies

`npm run deps` installs `requirements.txt` before the build. It is there for one
reason: `build_site.py` imports `watermark.py`, which needs **Pillow**, and
Cloudflare's build image ships Python without it. Without this step the deploy
dies at `import PIL` while the old site stays up — a failure that looks like
nothing happened.

`cairosvg` and `fonttools` are deliberately **not** in `requirements.txt`. They
serve only `tools/build_brand_assets.py`, which is run by hand when a mark
changes and whose output is committed, so the deploy never rasterises anything.

### If you do have a terminal

```bash
npm install
npm run check      # build + verify, including the browser checks
npm run preview    # serve public/ on :8787
npm run deploy     # build + verify + wrangler deploy
```

`npm run deploy` will not ship a build that fails `verify.py`.

### Why two verify modes

`verify.py` renders the page in Chromium to measure tap targets and confirm
images actually load. Cloudflare's build image has Python but no browser.
`--no-browser` skips that one section and substitutes static equivalents for the
two faults that ship broken — a missing image file and a second `h1`. Everything
else runs identically in both modes.

Run the full version before any change to layout or CSS.

---

## Layout

```
config.py           all content, and everything still outstanding
services.json       prices, as pulled from the live booking menu
build_site.py       generates public/
watermark.py        stamps the logo onto photographs at build time
verify.py           pre-deploy checks — deploy is gated on these
dedupe.py           is this photograph already in the gallery?
worker.js           www → apex, security and cache headers
instagram.js        optional daily Instagram → gallery sync
wrangler.toml       routes and the assets binding
requirements.txt    Pillow, for the build
tools/              run by hand, not by the build
photos/             MASTERS — clean, unwatermarked, never published as-is
brand/              logo masters and the derived photo marks
public/             GENERATED — never edit by hand (but see below)
```

Change content in `config.py`, never in `public/`.

**`public/` is committed on purpose.** It is still generated, and still must
never be hand-edited, but committing it means the repo always holds a deployable
site even if the build fails on Cloudflare — the one failure with no way out,
since there is no local Node to fall back on. Cloudflare regenerates it during
the build anyway. Treat it as a spare wheel, not the source.

---

## Brand controls

Maddy's brand guidelines are the authority, not this repo. The rules that matter
here, from her pack:

> **One name everywhere** (Nails by Maddy, not Nailsbymads) · **one booking
> link** · **logo never re-typed** · **clear space = height of the M** ·
> **minimum 28 mm / 110 px**

The build enforces what it can:

| Control | Where | What it stops |
|---|---|---|
| Logo is never re-typed | `brand/photo-mark-*.svg` are generated from the brand kit and vendored; nothing redraws type | A "close enough" logo drifting into the site |
| Brand colours only | `tools/build_brand_assets.py` refuses any fill that is not White, Polish Pink `#E8378A` or Ink `#141414` | A stray colour printing onto every photograph |
| Minimum size | Photo mark is 26% of image width = **312px** on a 1200px photo, **2.8× the 110px minimum** | The logo shrinking until "NAILS BY" is mush |
| Right colourway for the ground | `watermark.py` measures the corner and picks reversed (white) or primary (ink) | White type vanishing on a sunlit hand |
| Prices never retyped | `services.json` is the only source; `verify.py` fails if page and menu disagree | The site quoting a price her booking system doesn't |

### Known deviation

On the site's own gallery thumbnails (170–380px) the logo renders 44–99px,
**below the 110px minimum**. No watermark survives a 170px tile in spec. It is
in spec everywhere the stamp does its job — a saved copy, a repost, an Instagram
feed — and the thumbnail is one tap from the full-size version. If strict
compliance everywhere matters more, switch `watermark.MARK` to `"icon"`, which
is what an icon is for.

---

## Assets

### `photos/` — masters

Clean, unwatermarked, 1200×1200. **Never published as-is.** The watermark is
applied on the way out, so the stamp can be redesigned without re-cropping
nineteen photographs.

`photos/sources.json` records a perceptual fingerprint of the **original**
photograph each crop was made from. `dedupe.py` needs it; see below.

### `brand/` — marks

| File | Use |
|---|---|
| `nailsbymaddy-logo-primary.svg` | the logo, for light backgrounds |
| `nailsbymaddy-logo-reversed.svg` | the logo, for dark |
| `nailsbymaddy-icon-{32,180,512}.png` | favicon, touch icon, PWA |
| `nailsbymaddy-profile-badge.png` | social profile |
| `photo-mark-brand-dark.svg` | watermark, reversed colourway |
| `photo-mark-brand-light.svg` | watermark, primary colourway |
| `photo-mark-wordmark.svg` | watermark, mono white |
| `photo-mark-icon.svg` | watermark, monogram only |
| `outfit-600.ttf` | the address under the mark, in the site's own face |

The `photo-mark-*` files are **derived**. Regenerate with:

```bash
python3 tools/build_brand_assets.py
```

It rasterises each authored SVG and refuses anything that is not a brand colour.
`outfit-600.ttf` is decompressed from the site's own woff2 because Pillow cannot
read woff2 — the address on a photograph is set in the same type as the address
on the page.

### Published image names carry a content hash

`public/img/work-09.be4a262c.jpg`, not `work-09.jpg`.

These are served `max-age=31536000, immutable` — a promise to every browser and
every Cloudflare edge that the bytes behind the URL never change. Under fixed
filenames that promise was false: all nineteen photographs were once rewritten
under the names they already had, so any cache holding the old copy would have
served it **until 2027**. The hash makes the promise true — change the picture
and it is a different URL.

`verify.py` recomputes each hash from the published file and fails if the name
disagrees.

---

## Duplicate photographs

```bash
python3 dedupe.py ~/new-photos/*.jpg
```

Maddy sends batches from her camera roll without tracking what she has already
sent. Four batches in, three contained sets already up — one was three repeats
out of five.

**A file hash does not catch this.** The re-sends are re-exports: same
photograph, different bytes, different hash. Twice a hash check said "all new"
and only looking side by side caught it.

`dedupe.py` compares what the picture *looks like* — a difference hash, which
survives re-export, re-compression and resizing. It compares **full frame
against full frame**, using `photos/sources.json`, because `photos/` holds square
crops and a candidate arrives uncropped; comparing the two directly once passed a
re-send whose source file was byte-identical to one already up.

Threshold is measured, not guessed: every confirmed re-send scored **0**, the
closest genuinely different pair scored **13**, so it sits at **8**.

**Add a photograph → add its source fingerprint**, or the check silently
weakens. `work-03` and the portrait predate the manifest and the script prints
that blind spot on every run.

---

## SEO and keywords

Westcliff is where she is. **Southend is what gets searched.**

| Term | Monthly volume |
|---|---|
| `nail salon southend` | 590 |
| `nails southend on sea` | 320 |
| `nail salon westcliff on sea` | 10 |

Both towns are in the title; Southend earns its place on volume, Westcliff on
being the truth and what the map pack matches. Title and description are held
inside what Google actually displays — **title ≤ 62 characters, description
120–158** — and `verify.py` fails outside that.

Terms the copy must keep, with minimum counts, enforced on every build:

```
southend ×3   westcliff ×3   builder gel ×3
hard gel ×2   gel nails ×1   nail technician ×1
```

Structured data is `NailSalon` with a full `hasOfferCatalog` of all 20 services
and a `FAQPage`. Every price in the schema is cross-checked against
`services.json`.

Each gallery photograph opens a detail panel naming its **nail art tier** and
what that tier costs, so the gallery carries the price list rather than sitting
apart from it. Tier prices are read from `services.json` at build time, never
typed.

> ⚠ **The tier on each photograph is not yet confirmed by Maddy.** They were
> read off the images against her own tier descriptions. The checks verify that
> the *price matches the tier claimed* — they cannot tell whether the tier suits
> the picture. Her sign-off is required before `DRAFT` flips to `False`.

---

## Caching

| Served | Cache-Control | Why |
|---|---|---|
| Photographs, fonts, logos | `max-age=31536000, immutable` | names carry a content hash, so this is honest |
| HTML, txt, xml | `max-age=0, must-revalidate` **+ `Cloudflare-CDN-Cache-Control: no-store`** | see below |

Cloudflare's edge read `public` on the HTML and cached the page — **and strips
the query string from the cache key**, so even a cache-busting `?x=` came back
`HIT`. After a deploy each datacentre served its own stale copy: whoever
deployed saw the new site from their edge while someone in another city still
saw the old one, and nothing looked broken.

`Cloudflare-CDN-Cache-Control` is read only by their edge and overrides the line
above for it alone, so browsers revalidate exactly as before. Applied to
documents by **exclusion, not by suffix** — the page that matters most is `/`
and it has no extension.

`public/_redirects` is gitignored. Workers Assets rejects absolute URLs in it
(`code: 100324`) and it killed a deploy once — then came back twice, because a
folder upload and a `git add public/` each re-added it. `worker.js` does the www
redirect; the ignore rule is there so it cannot return a fourth time.

---

## The draft flag

`DRAFT = True` in `config.py` is a safety catch, not a convenience:

| | `DRAFT = True` | `DRAFT = False` |
|---|---|---|
| Missing content | dashed "to supply" blocks | section omitted entirely |
| Ribbon | shown | none |
| Robots | `noindex` + `Disallow: /` | indexable, sitemap declared |
| Reviews | all three | only the publicly-posted one |

`verify.py` builds a throwaway live copy on every run and **fails** if a
placeholder, the ribbon, or an unconfirmed review would reach production.

---

## What verify.py checks

**Content**
- All 20 prices match `services.json` in both the page and the JSON-LD
- Every service in the booking menu appears on the page
- FAQs match the FAQPage schema exactly
- Target search terms still present, at minimum counts

**Presentation**
- Title ≤ 62 characters, description 120–158
- One `h1`, headings in order, every image loads, tap targets ≥ 44px
- CTA order correct, first one primary, `wa.me` number has no leading zero or `+`

**Gallery**
- Every photograph has a note; every note renders
- Every tile links to a panel that exists; no panel is orphaned
- The price shown matches the tier claimed
- **No `<script>` tag** — the CSP would kill it silently and the panels would
  look broken to everyone except whoever added it

**Photographs**
- Every gallery photograph is watermarked; the portrait is not
- Every published name matches a hash of its own bytes

The watermark check measures **how much** the corner changed against an
untouched control area, not whether it changed at all. An earlier version asked
"do any pixels differ" and passed a build whose stamp was a no-op — re-saving a
JPEG re-encodes it, so a few pixels differ everywhere even when nothing was
drawn. The floor has been re-measured **six times** as the mark changed; a
measured threshold does not fail when it goes stale, it just quietly stops
meaning anything. **Re-measure whenever the mark changes.**

---

## Still outstanding

| Item | Blocks |
|---|---|
| `booking_url` in `config.py` | Every Book button — falls back to WhatsApp meanwhile |
| Maddy's sign-off on the 19 nail art tiers | `DRAFT = False` |
| Review permissions from Sarah and Paula | Two of the three reviews going live |
| Kizuri's OK on the address | Using the salon address publicly |
| Google Business Profile access | Map pack, reviews, hours |
| Insurance certificate | Currently her word for it |
| A men's manicure price | The gallery shows a men's set; the menu has only a men's pedicure |

**Diary note — early October:** Thursday flips to winter hours. The page states
both windows in plain English so it stays truthful either way, but the
structured data carries only the window in force at build time. It needs a
rebuild to stay accurate for Google.

---

## Decisions worth not relitigating

- **`NailSalon`, not `LocalBusiness`** in the schema. The specific type wins.
- **No `aggregateRating`.** One review is not a rating, and self-serving review
  markup breaks Google's guidelines. It belongs on the Google profile.
- **Prices come from `services.json`**, never retyped.
- **"BIAB" is a trademark** of The Gel Bottle Inc, not a generic term. The site
  says "builder gel" unless Maddy uses their product; the first FAQ explains the
  difference honestly. She uses Twenty Pro and American Creator hard gels.
- **Wordmarks are `<img>`, not inline SVG.** Outlined type, 37 KB of path data
  each; svgo takes them to 9 KB with no visible change.
- **CTA order: Book online → WhatsApp → Call**, only the ones that exist
  rendered. Until a booking system is chosen WhatsApp leads, because most people
  would rather message a nail tech than ring one — and it leaves her a written
  record. Call never disappears.
- **Detail panels use CSS `:target`, not JavaScript.** The CSP forbids scripts,
  the back button closes the panel, every word is in the HTML for Google, and
  the panel reuses the tile's image file so the feature costs no extra bytes.
- **The portrait is never watermarked.** It is Maddy's own face on her own site;
  a stamp there reads as a stock photo.

---

## Instagram sync

Off by default. `instagram.js` pulls her latest posts on a daily cron, copies the
images into R2, and injects them with `HTMLRewriter` so real `<img>` tags with
alt text are in the HTML Google receives — a client-side widget would be an empty
div to a crawler.

Three constraints in the code, all deliberate:

1. **Never hotlink `media_url`.** Instagram's CDN links are signed and expire.
2. **Never blank the gallery.** The token lasts 60 days and refreshes at 14
   remaining; any sync failure is logged and swallowed, last good images stay.
3. **Alt text is not the caption.** Hashtags and emoji stripped, plain fallback.

To switch on: Instagram account to professional (free, same handle — and per
Meta's docs this API needs no linked Facebook Page), create a Meta app, run the
OAuth once, `wrangler secret put IG_TOKEN`, then uncomment the KV and R2 bindings
in `wrangler.toml`.

---

## Mail

Not served by this Worker — `nailsbymaddy.co.uk` mail is Openprovider Mailcow,
relayed outbound through Amazon SES. Records live in the Cloudflare zone, never
in Openprovider's zone editor, and no mail record is ever proxied.
