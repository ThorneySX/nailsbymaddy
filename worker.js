/**
 * nailsbymaddy.co.uk — static site edge worker.
 *
 * Cloudflare serves everything in public/ directly. This does the three things
 * the assets binding won't: fold www into the apex, attach security and
 * caching headers, and splice the Instagram gallery into the page on the way
 * out so the images are in the HTML Google receives.
 */

import { sync, injectGallery, serveMedia } from './instagram.js';

const CANONICAL = 'nailsbymaddy.co.uk';

/**
 * Content-addressed assets can cache hard; HTML must not.
 *
 * Photographs are published with a hash of their bytes in the filename, so
 * `immutable` for a year is a promise we can actually keep: change the
 * picture and it is a different URL. Under fixed names it was a lie — all
 * nineteen photographs were rewritten under the names they already had, and
 * any edge holding the old copy would have served it until 2027.
 */
const CACHE = [
  [/\.(woff2|svg|png|jpg|webp|ico)$/i, 'public, max-age=31536000, immutable'],
  [/\.(html?|txt|xml)$/i, 'public, max-age=0, must-revalidate'],
];

/**
 * Keep the HTML out of Cloudflare's own edge cache entirely.
 *
 * `max-age=0, must-revalidate` is aimed at browsers and it is right for
 * them. Cloudflare's edge read `public` and cached the page anyway — and it
 * strips the query string from the cache key, so even a cache-busting `?x=`
 * came back HIT. The effect after a deploy is that each datacentre keeps
 * serving its own stale copy: one person sees the new site, another in a
 * different city still sees the old one, and nothing about it looks broken.
 *
 * Cloudflare-CDN-Cache-Control is read only by their edge and overrides the
 * line above for it alone, so browsers keep revalidating exactly as before
 * and the CDN stops holding the page. The site is one small document; there
 * is nothing to gain by caching it at the edge and a stale launch to lose.
 */
const NO_EDGE_CACHE = /\.(html?|txt|xml)$/i;

const SECURITY = {
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'strict-origin-when-cross-origin',
  'strict-transport-security': 'max-age=31536000; includeSubDomains',
  // No third-party anything — fonts, styles and images are all same-origin,
  // Instagram's included, because we copy them into R2 rather than hotlinking.
  'content-security-policy':
    "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data:; font-src 'self'; form-action 'none'; " +
    "frame-ancestors 'none'; base-uri 'none'",
  'permissions-policy': 'geolocation=(), microphone=(), camera=(), interest-cohort=()',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.hostname !== CANONICAL) {
      url.hostname = CANONICAL;
      return Response.redirect(url.toString(), 301);
    }

    // /media/ only exists once the Instagram bindings are switched on.
    if (url.pathname.startsWith('/media/')) {
      if (!env.MEDIA) return new Response('Not found', { status: 404 });
      return serveMedia(env, url);
    }

    let res = await env.ASSETS.fetch(request);

    // Only the home page has a gallery to fill.
    if (url.pathname === '/' && env.IG) {
      const manifest = await env.IG.get('ig:manifest', 'json').catch(() => null);
      res = injectGallery(res, manifest);
    }

    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(SECURITY)) out.headers.set(k, v);

    const rule = CACHE.find(([re]) => re.test(url.pathname));
    out.headers.set('cache-control', rule ? rule[1] : 'public, max-age=0, must-revalidate');

    // The home page is '/' — no extension — so test the path for a document
    // by exclusion rather than by suffix, or the one page that matters most
    // is the one that keeps getting cached.
    const isDoc = NO_EDGE_CACHE.test(url.pathname) || !/\.[a-z0-9]+$/i.test(url.pathname);
    if (isDoc) out.headers.set('cloudflare-cdn-cache-control', 'no-store');

    return out;
  },

  /**
   * Daily Instagram pull. A failure here is logged and swallowed: the previous
   * manifest and its R2 images stay live, so the gallery never goes blank
   * because of one bad night.
   */
  async scheduled(event, env, ctx) {
    if (!env.IG || !env.MEDIA) return;   // bindings not switched on yet
    ctx.waitUntil(
      sync(env)
        .then((r) => console.log('instagram sync ok', r.count, 'images'))
        .catch((e) => console.error('instagram sync failed, keeping last good gallery:', e.message))
    );
  },
};
