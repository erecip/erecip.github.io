/**
 * Cloudflare Pages Edge Worker (_worker.js)
 * ============================================================
 * - Serves ALL page requests with HTTP 200 OK (no 302 redirects)
 * - Provides internal /_edge/read API for client-side navigation
 * - Bots and redirect-checkers receive 200 OK without any redirect headers
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const userAgent = request.headers.get("user-agent") || "";

    // 1. Internal Edge API endpoint for human navigation
    if (url.pathname === "/_edge/read") {
      const isBot = /bot|crawl|spider|slurp|google|bing|yandex|baidu|facebook|pinterestbot|whatsapp|preview|headless|phantom|puppet|lighthouse|wheregoes/i.test(userAgent);
      if (isBot) {
        // Return harmless empty response to bots
        return new Response(JSON.stringify({ status: "ok" }), {
          headers: { "content-type": "application/json", "cache-control": "no-store" }
        });
      }

      // Real user request: provide destination URL
      const pathParam = url.searchParams.get("p") || "";
      const cleanPath = pathParam.startsWith("/") ? pathParam : "/" + pathParam;
      const target = "https://schnellrezept.com" + cleanPath;
      return new Response(JSON.stringify({ target }), {
        headers: { "content-type": "application/json", "cache-control": "no-store" }
      });
    }

    // 2. For ALL other requests (HTML articles, root, images, etc.):
    // ALWAYS serve static files with HTTP 200 OK!
    return env.ASSETS.fetch(request);
  }
};
