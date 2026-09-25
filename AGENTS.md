# Working on this repo

Read this before changing anything. It is the short version of decisions that
were expensive to learn, and the list of things that must not be broken.

`README.md` explains how the site works. This file explains what you are not
allowed to do to it, and why.

---

## The one-paragraph brief

`nailsbymaddy.co.uk` is a one-page static site for **Maddy Coram**, a
self-employed nail technician working from Kizuri Beauty Parlour in
Westcliff-on-Sea. Eight years in the trade, Level 2 and 3 qualified, natural
nails only — gel, builder gel, hard gel, nail art, spa pedicures, **no
acrylics**. It is the first full "The Lot" delivery for **WinCustomers**
(Outstanding Group), built as the template for every customer after her.
British English, in her voice: warm, plain, no salon jargon.

The site's job is to turn someone who found her into someone who messages her.
Everything else is secondary to that.

---

## Controls

These are invariants. If a change requires breaking one, stop and ask —
do not work around it.

### Brand

1. **The logo is never re-typed, redrawn, or recut.** Her guidelines say so.
   This was broken once: the "NAILS BY" line was deleted from the photo mark
   because it measured badly at a chosen size. That took the name of the
   business off her own photographs. **The size is the variable. The logo is
   not.**
2. **Minimum size 110px** (28mm). The photo mark runs at 312px, 2.8× that.
3. **Brand colours only** — Polish Pink `#E8378A`, Blush `#FCE4EE`, Ink
   `#141414`, White. `tools/build_brand_assets.py` refuses anything else and
   that refusal is deliberate.
4. **One name everywhere**: Nails by Maddy. Never "Nailsbymads" in copy.
5. Wordmarks are `<img>`, never live text and never inline SVG.

### Legal and factual

6. **Prices are never typed.** They come from `services.json`, which is her
   live booking menu. `verify.py` fails if the page and the menu disagree.
   Changing a price is her decision made in her booking system, not ours.
7. **"BIAB" is a trademark** of The Gel Bottle Inc, not a generic term. She
   uses Twenty Pro and American Creator. The first FAQ explains the difference
   honestly. Never describe her work as BIAB.
8. **Supplier marks are published byte-for-byte as supplied.** Twenty and
   American Creator are other companies' trademarks. Do not recolour, restyle,
   crop or watermark them, and **claim no relationship** — no "partner",
   "approved", "official stockist". `verify.py` enforces both.
9. **No review is published without that client's permission.** Two of the
   three are unconfirmed and are hidden by `DRAFT`. Do not surface them.
10. **No `aggregateRating` in the schema.** One review is not a rating, and
    self-serving review markup breaks Google's guidelines.
11. **Never claim a qualification, insurer or awarding body she has not
    stated.** A certificate visible in a photograph is not a statement.

### Technical

12. **No JavaScript on the page.** The CSP is `script-src 'none'`. The nav and
    the gallery panels are CSS `:target`. `verify.py` fails on a `<script>`
    tag, because the CSP would kill it silently and the page would look broken
    to everyone except whoever added it.
13. **`photos/` are clean masters.** The watermark is applied at build time on
    the way to `public/img/`. Never stamp a master.
14. **The portrait is never watermarked.** It is her own face on her own site.
15. **Published photo names carry a content hash** and are served `immutable`
    for a year. Under fixed names that promise was false and a stale photo
    would have been served until 2027. If you change how images are written,
    keep the hash.
16. **`public/_redirects` must never be committed.** Workers Assets rejects
    absolute URLs in it (`code: 100324`); it has killed a deploy and come back
    twice. It is gitignored. `worker.js` does the www redirect.
17. **`public/` is generated but committed** — deliberately, as a deployable
    spare wheel if the Cloudflare build fails. Never hand-edit it.
18. **`verify.py` must pass before any deploy.** No exceptions, no `--force`.

### Measured thresholds go stale silently

19. `verify.py` has thresholds derived from measurement, not judgement — the
    watermark detection floor (moved **six times**) and `dedupe.py`'s
    similarity threshold. **A measured threshold does not fail when it goes
    stale. It quietly stops meaning anything.** If you change the mark's size,
    opacity or shape, re-measure the floor and write the new numbers into the
    comment.

---

## Before you add photographs

Run `python3 dedupe.py <files>` first. Four batches arrived, three contained
sets already on the site. **A file hash cannot catch this** — the re-sends are
re-exports, so same picture, different bytes. Twice a hash check said "all new"
and only looking side by side caught it.

Then add the source fingerprint to `photos/sources.json`, or the check silently
weakens for the next batch.

---

## How to work

1. `npm install` once, then `npm run check` — build plus every check including
   the browser ones. On Cloudflare it is `npm run ci`, which skips only the
   rendered measurements.
2. Content changes go in `config.py`. Nothing else.
3. Prices change in her booking system, then `services.json`.
4. Commit messages explain **why**, especially when something was wrong before.
   The history is the reasoning; a future agent reads it to avoid repeating a
   mistake.
5. When a check fails, fix the code — not the check. The one time it is right
   to change a check is when the check itself is measuring the wrong thing,
   and then say so in the commit.

---

## What is not ours to decide

Stop and ask Andy (andyt@outstanding-group.com) before:

- Publishing any review without documented permission.
- Setting `DRAFT = False`. The site is currently `noindex`; that is the **only
  remaining signal** that it is not live, since the draft ribbon was removed.
- Changing a price.
- Anything touching the salon's systems, Kizuri's Google listing, or the
  salon's Ovatu account.
- Spending anything on Maddy's behalf.
- Claiming a relationship with a supplier.
- Setting DNSSEC.

---

## The one commercial fact worth knowing

Maddy books through **Kizuri's Ovatu account**, so the booking record and the
client relationship sit with the salon, not with her. The standard UK
chair-rental agreement is asymmetric: it stops the renter soliciting the
salon's clients, with no matching restriction the other way.

This is why `booking_url` is still empty, and why **WhatsApp is the primary
call to action** — it is a channel she owns. Do not quietly point the Book
button at the salon's system to tidy up the outstanding list. That decision is
hers and Andy's, and it is a commercial one, not an admin one.
