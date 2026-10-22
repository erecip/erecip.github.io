/**
 * Cloudflare Pages Edge Worker (_worker.js)
 * ============================================================
 * Handles intelligent edge redirection for human visitors
 * while serving static pages (with Schema JSON-LD & Open Graph)
 * to search bots, crawlers, and Rich Results testers.
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const userAgent = request.headers.get("user-agent") || "";

    // Bot detection filter:
    // - Keeps Google WRS / Googlebot / Facebook / etc. broad so they see the full static page
    // - Uses 'pinterestbot' (specific) so real human Pinterest in-app browser visitors are redirected
    const isBot = /bot|crawl|spider|slurp|google|bing|yandex|baidu|facebook|pinterestbot|whatsapp|preview|headless|phantom|puppet|lighthouse/i.test(userAgent);

    // 1. Static assets & media (images, fonts, stylesheets, icons, etc.)
    // Always serve directly from Cloudflare Pages static asset storage
    if (url.pathname.match(/\.(png|jpe?g|webp|gif|svg|ico|css|js|txt|xml|woff2?|ttf|eot)$/i)) {
      return env.ASSETS.fetch(request);
    }

    // 2. Bots, crawlers, and SEO / Rich Results testers
    // Serve clean static HTML page (HTTP 200 OK) with full schema markup and meta tags
    if (isBot) {
      return env.ASSETS.fetch(request);
    }

    // 3. Human users visiting recipe article pages (/en/...)
    // Perform instant edge HTTP 302 redirect, preserving path and all tracking parameters
    if (url.pathname.startsWith("/en/")) {
      const destination = "https://schnellrezept.com" + url.pathname + url.search;
      return Response.redirect(destination, 302);
    }

    // 4. Human users visiting root with ?id=/en/... query param
    const idParam = url.searchParams.get("id");
    if (idParam) {
      const cleanPath = idParam.startsWith("/") ? idParam : "/" + idParam;
      const destination = "https://schnellrezept.com" + cleanPath + url.search;
      return Response.redirect(destination, 302);
    }

    // 5. Default fallback (e.g. homepage or other static assets)
    return env.ASSETS.fetch(request);
  }
};
