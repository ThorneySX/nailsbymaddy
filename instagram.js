/**
 * Instagram → the Recent sets gallery.
 *
 * Runs on a daily cron. Pulls Maddy's latest posts, copies the images into R2,
 * and writes a manifest to KV. The request handler then injects real <img>
 * tags into the page with HTMLRewriter, so Google sees actual images on
 * nailsbymaddy.co.uk — not a third-party script it can't read.
 *
 * Three things drove the design:
 *
 * 1. NEVER HOTLINK. Instagram's media_url is a signed CDN link. Meta don't
 *    document a lifetime, but the signatures do expire — their own developer
 *    forum is full of it. A site pointing at those URLs shows broken images a
 *    few days later. So every image is copied into R2 and served from our own
 *    domain, which is also the only version Google will index.
 *
 * 2. NEVER EMPTY THE GALLERY. The long-lived token lasts 60 days. If a refresh
 *    ever fails — revoked access, changed password, Meta outage — the sync
 *    stops. The last good manifest and its images stay in place and the site
 *    carries on looking finished while we fix it.
 *
 * 3. ALT TEXT IS NOT THE CAPTION. Instagram captions are hashtags and emoji.
 *    We strip those; if nothing sensible is left, we fall back to a plain
 *    description rather than publishing "💅✨ #nailsofinstagram" as alt text.
 *
 * Bindings (wrangler.toml): IG (KV), MEDIA (R2)
 * Secrets: IG_TOKEN — the long-lived token from the one-off OAuth
 */

const GRAPH = 'https://graph.instagram.com';
const COUNT = 9;                    // 3×3 grid
const KEY = 'ig:manifest';
const TOKEN_KEY = 'ig:token';

/* ------------------------------------------------------------------ token */

/**
 * Long-lived tokens last 60 days and can be refreshed once they're 24h old.
 * We refresh whenever there's under 14 days left, which gives roughly a
 * fortnight of failed attempts before anything actually breaks.
 */
async function token(env) {
  const stored = await env.IG.get(TOKEN_KEY, 'json');
  const current = stored?.value ?? env.IG_TOKEN;
  const daysLeft = stored ? (stored.expires - Date.now()) / 864e5 : 0;

  if (stored && daysLeft > 14) return current;

  const r = await fetch(
    `${GRAPH}/refresh_access_token?grant_type=ig_refresh_token&access_token=${current}`
  );
  if (!r.ok) {
    // Refreshing failed. Carry on with the token we have — it may still have
    // weeks left — and let the next run try again.
    console.error('ig token refresh failed', r.status, await r.text());
    return current;
  }
  const j = await r.json();
  await env.IG.put(TOKEN_KEY, JSON.stringify({
    value: j.access_token,
    expires: Date.now() + j.expires_in * 1000,
  }));
  return j.access_token;
}

/* -------------------------------------------------------------- alt text */

const ALT_FALLBACK = 'A set of nails by Maddy';

function altFrom(caption) {
  if (!caption) return ALT_FALLBACK;
  const clean = caption
    .replace(/#[\w]+/g, ' ')                               // hashtags
    .replace(/@[\w.]+/g, ' ')                              // handles
    .replace(/[\p{Extended_Pictographic}\p{Emoji_Presentation}]/gu, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const first = clean.split(/(?<=[.!?])\s/)[0] ?? '';
  // Anything shorter than a few words is decoration, not a description.
  if (first.split(' ').length < 3) return ALT_FALLBACK;
  return first.length > 120 ? first.slice(0, 117).trimEnd() + '…' : first;
}

/* ----------------------------------------------------------------- sync */

export async function sync(env) {
  const t = await token(env);

  const url = `${GRAPH}/me/media?fields=id,media_type,media_url,permalink,caption,timestamp&limit=25&access_token=${t}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`instagram media: ${r.status} ${await r.text()}`);

  const { data = [] } = await r.json();
  // Photos only. Videos need a poster frame and a player; not worth it here.
  const posts = data.filter((m) => m.media_type === 'IMAGE').slice(0, COUNT);
  if (!posts.length) throw new Error('instagram returned no images — refusing to blank the gallery');

  const previous = (await env.IG.get(KEY, 'json')) ?? { items: [] };
  const known = new Map(previous.items.map((i) => [i.id, i]));
  const items = [];

  for (const p of posts) {
    const hit = known.get(p.id);
    if (hit) { items.push(hit); continue; }          // already in R2, leave it

    const img = await fetch(p.media_url);
    if (!img.ok) { console.error('ig image fetch failed', p.id, img.status); continue; }

    const key = `ig/${p.id}.jpg`;
    await env.MEDIA.put(key, img.body, {
      httpMetadata: {
        contentType: img.headers.get('content-type') ?? 'image/jpeg',
        cacheControl: 'public, max-age=31536000, immutable',
      },
    });
    items.push({ id: p.id, key, alt: altFrom(p.caption), permalink: p.permalink, at: p.timestamp });
  }

  if (!items.length) throw new Error('nothing downloaded — keeping the previous manifest');

  await env.IG.put(KEY, JSON.stringify({ items, synced: new Date().toISOString() }));

  // Tidy up images that have dropped off the end of the grid.
  for (const old of previous.items) {
    if (!items.some((i) => i.id === old.id)) await env.MEDIA.delete(old.key).catch(() => {});
  }

  return { count: items.length };
}

/* ------------------------------------------------------------- rendering */

const escape = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function tiles(items) {
  return items.map((i) =>
    `<figure class="tile"><a href="${escape(i.permalink)}" rel="noopener"` +
    ` aria-label="See this set on Instagram">` +
    `<img src="/media/${escape(i.key)}" alt="${escape(i.alt)}" loading="lazy"` +
    ` decoding="async" width="600" height="600"></a></figure>`
  ).join('');
}

/**
 * Swap the gallery placeholder for the real grid on the way out. The HTML
 * leaves the origin with real <img> tags in it, which is the whole point —
 * a client-side widget would be invisible to Google.
 */
export function injectGallery(response, manifest) {
  if (!manifest?.items?.length) return response;
  return new HTMLRewriter()
    .on('#work .wrap', {
      element(el) { el.setInnerContent(
        `<h2>Recent sets</h2><div class="grid">${tiles(manifest.items)}</div>` +
        `<p class="note">Straight from Instagram — updated daily.</p>`,
        { html: true });
      },
    })
    .transform(response);
}

/** Serve an image out of R2 at /media/ig/<id>.jpg */
export async function serveMedia(env, url) {
  const key = url.pathname.replace(/^\/media\//, '');
  const obj = await env.MEDIA.get(key);
  if (!obj) return new Response('Not found', { status: 404 });
  const h = new Headers();
  obj.writeHttpMetadata(h);
  h.set('etag', obj.httpEtag);
  h.set('cache-control', 'public, max-age=31536000, immutable');
  return new Response(obj.body, { headers: h });
}
