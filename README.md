# nailsbymaddy.co.uk

One page, static, served from a Cloudflare Worker. No framework, no JavaScript
on the page, no third-party requests — fonts and logos are self-hosted, which is
why the CSP can be `default-src 'self'; script-src 'none'`.

87 KB cold, about 11 KB over the wire. No layout shift; every image is
dimensioned.

## Deploying — no terminal needed

This repo is connected to a Cloudflare Worker through **Workers Builds**.
Cloudflare runs the build on their machines, so nothing needs installing
anywhere. **Push to `main` and the site deploys.** Edit a file on github.com
in a browser and that counts as a push.

Settings on the Cloudflare side, under the Worker → Settings → Builds:

| Field | Value |
|---|---|
| Build command | `npm ci --include=dev && npm run ci` |
| Deploy command | `npx wrangler deploy` |
| Root directory | `/` |
| Production branch | `main` |

`npm run ci` is `build_site.py` then `verify.py --no-browser`. A failing
check exits non-zero, Cloudflare stops, and **nothing deploys** — the same
gate as locally, minus the rendered measurements (see below).

### If you do have a terminal

```bash
npm install
npm run check      # build + verify, including the browser checks
npm run preview    # serve public/ on :8787
npm run deploy     # build + verify + wrangler deploy
```

`npm run deploy` will not ship a build that fails `verify.py`.

### Why two modes

`verify.py` renders the page in Chromium to measure tap targets and confirm
images actually load. Cloudflare's build image has Python but no browser, and
installing one would add minutes to every deploy to re-measure a layout that
has not changed. `--no-browser` skips that one section and substitutes static
equivalents for the two faults that ship broken — a missing image file and a
second `h1`. Everything else, including the whole price cross-check and the
draft-leak test, runs identically in both modes.

Run the full version before any change to layout or CSS.

## Layout

```
config.py        all content, and everything still outstanding
build_site.py    generates public/
verify.py        pre-deploy checks — deploy is gated on these
worker.js        www → apex, security and cache headers
instagram.js     optional daily Instagram → gallery sync
wrangler.toml    routes and the assets binding
brand/           logo masters
services.json    prices, as pulled from the live booking menu
public/          GENERATED — gitignored, never edit by hand
```

Change content in `config.py`, never in `public/`. That folder is derived
entirely from `config.py`, `services.json` and `brand/`, and is rebuilt from
scratch each time.

## The draft flag

`DRAFT = True` in `config.py` is a safety catch, not a convenience:

| | `DRAFT = True` | `DRAFT = False` |
|---|---|---|
| Missing content | dashed "to supply" blocks | section omitted entirely |
| Ribbon | shown | none |
| Robots | `noindex` + `Disallow: /` | indexable, sitemap declared |
| Reviews | all three | only the publicly-posted one |

So a half-finished site can be shared for review but cannot accidentally go
live looking unfinished. `verify.py` builds a throwaway live copy on every run
and **fails** if a placeholder, the ribbon, or an unconfirmed review would reach
production.

## What verify.py actually checks

- All 20 prices match `services.json` in both the page and the JSON-LD
- Every service in the booking menu appears on the page
- FAQs match the FAQPage schema exactly
- Title ≤ 62 characters, description 120–158 — Google's display limits
- One `h1`, headings in order, every image loads, tap targets ≥ 44px
- CTA order correct, first one primary, `wa.me` number has no leading zero or `+`
- Target search terms still present in the copy

## Still outstanding

Each is a key in `OUTSTANDING` in `config.py`. Fill it in, rebuild.

| Key | Blocks |
|---|---|
| `booking_url` | Every Book button — falls back to WhatsApp meanwhile |
| `hours` | Find me, and opening hours in the schema |
| `gallery` | Recent sets |
| `portrait` | About |
| `qualifications` + `insurer` | About, footer |
| `builder_gel_brand` | Whether we may say "BIAB" |

## Decisions worth not relitigating

- **`NailSalon`, not `LocalBusiness`** in the schema. The specific type wins.
- **No `aggregateRating`.** One review is not a rating, and self-serving review
  markup breaks Google's guidelines. It belongs on the Google profile, where
  Google reads it itself.
- **Prices come from `services.json`**, pulled from the live booking menu, never
  retyped. `verify.py` fails if the page and the menu disagree.
- **"BIAB" is a trademark** of The Gel Bottle Inc, not a generic term for
  builder gel. The site says "builder gel" unless Maddy uses their product; the
  first FAQ explains the difference honestly.
- **Wordmarks are `<img>`, not inline SVG.** Outlined type, 37 KB of path data
  each — inlining two would put 74 KB in front of the parser. svgo takes them to
  9 KB with no visible change.
- **CTA order: Book online → WhatsApp → Call**, first one primary, only the ones
  that exist rendered. Booking online is least friction; until a system is
  chosen WhatsApp leads, because most people would rather message a nail tech
  than ring one — and it leaves her a written record. Call never disappears.

## Instagram sync

Off by default. `instagram.js` pulls her latest posts on a daily cron, copies
the images into R2, and injects them with `HTMLRewriter` so real `<img>` tags
with alt text are in the HTML Google receives — a client-side widget would be an
empty div to a crawler.

Three constraints in the code, all deliberate:

1. **Never hotlink `media_url`.** Instagram's CDN links are signed and expire.
2. **Never blank the gallery.** The token lasts 60 days and refreshes at 14
   remaining; any sync failure is logged and swallowed, last good images stay.
3. **Alt text is not the caption.** Hashtags and emoji stripped, plain fallback.

To switch on: Instagram account to professional (free, same handle — and per
Meta's docs this API needs no linked Facebook Page), create a Meta app, run the
OAuth once, `wrangler secret put IG_TOKEN`, then uncomment the KV and R2
bindings in `wrangler.toml`.

## Mail

Not served by this Worker — `nailsbymaddy.co.uk` mail is Openprovider Mailcow,
relayed outbound through Amazon SES. Records live in the Cloudflare zone, never
in Openprovider's zone editor, and no mail record is ever proxied.
