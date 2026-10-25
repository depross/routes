#!/usr/bin/env python3
"""Build index.html (region > category > route) from the meta.json files the route builds write."""
import json, glob, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
metas = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, "*", "*", "meta.json")))]
SIZE_ORDER = {"S": 0, "M": 1, "L": 2, "XL": 3}
CAT_CUE = {"Nature": "woods, hop fields, the old railway", "History": "the town behind the Ypres Salient",
           "City": "the old cloth and hop town", "Beer & hops": "what the fields are for", "Border": "two countries, one plain"}
CAT_ORDER = ["Nature", "History", "City", "Beer & hops", "Border"]
REGION_CUE = {"poperinge": "From the front door, Kleine Dasdreef."}

regions = {}
for m in metas:
    r = regions.setdefault(m["region_slug"], {"name": m["region"], "slug": m["region_slug"], "cue": REGION_CUE.get(m["region_slug"], ""), "cats": {}})
    c = r["cats"].setdefault(m["category"], {"name": m["category"], "slug": m["category"].lower().replace(" & ", "-").replace(" ", "-"), "cue": CAT_CUE.get(m["category"], ""), "routes": []})
    c["routes"].append(m)
for r in regions.values():
    cats = sorted(r["cats"].values(), key=lambda c: CAT_ORDER.index(c["name"]) if c["name"] in CAT_ORDER else 99)
    for c in cats: c["routes"].sort(key=lambda m: SIZE_ORDER.get(m["size"], 9))
    r["cats"] = cats
DATA = json.dumps(list(regions.values()), ensure_ascii=False)

page = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#000000">
<style>:root{color-scheme:dark}body{margin:0}[hidden]{display:none!important}</style>
<title>Routes</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500&family=Fraunces:ital,opsz,wght@1,9..144,300;1,9..144,400&family=Rubik+Distressed&display=swap">
<style>
  :root { --bg:#000; --fg:#EDE8E1; --muted:#A8A197; --dim:#7C756D; --line:#2A2724; --orange:#E85D1F;
    --font-body:"Geist","Helvetica Neue",Arial,sans-serif; --font-accent:"Fraunces",Georgia,serif; --font-mark:"Rubik Distressed","Geist",sans-serif; color-scheme:dark; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font-family:var(--font-body); font-weight:300; font-size:16px; line-height:1.5; -webkit-font-smoothing:antialiased; }
  body::after { content:""; position:fixed; inset:0; pointer-events:none; z-index:1; opacity:.09;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='160' height='160' filter='url(%23n)' opacity='1'/></svg>"); background-size:160px 160px; }
  a { color: inherit; }
  a:focus-visible { outline:1px solid var(--fg); outline-offset:3px; }
  .page { max-width:560px; margin:0 auto; padding:0 max(16px, env(safe-area-inset-left,0px)) 56px; min-height:100vh; display:flex; flex-direction:column; }
  .hero { padding-block: 56px 28px; display:grid; gap:12px; }
  .crumbs { display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:400; margin:0; min-height:1.5em; }
  .crumbs a { color:var(--muted); text-decoration:none; border-bottom:1px solid var(--line); padding-bottom:1px; }
  .crumbs a:hover { color:var(--fg); }
  .crumbs .sep { color:var(--dim); }
  .crumbs b { color:var(--fg); font-weight:400; }
  .hero h1 { font-weight:300; font-size:clamp(44px,13vw,76px); line-height:.95; margin:0; letter-spacing:-.03em; text-wrap:balance; }
  .hero h1 em { font-family:var(--font-accent); font-style:italic; font-weight:300; color:var(--orange); letter-spacing:0; }
  .hero .sub { font-family:var(--font-accent); font-style:italic; font-weight:300; font-size:19px; color:var(--muted); margin:0; }
  .step { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:500; margin:0 0 8px; }
  .step i { font-family:var(--font-accent); font-style:italic; font-weight:300; font-size:15px; letter-spacing:0; text-transform:none; color:var(--dim); }
  .list { border-top:1px solid var(--line); display:grid; }
  .card { display:grid; grid-template-columns:1fr auto; gap:4px 16px; align-items:center; padding:20px 0; border-bottom:1px solid var(--line); text-decoration:none; color:inherit; position:relative; }
  .card:hover .title, .card:focus-visible .title { color:var(--orange); }
  .card .where { grid-column:1; font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:500; }
  .card .where .draft { color:var(--orange); }
  .card .title { grid-column:1; font-size:24px; font-weight:300; line-height:1.15; margin:0; transition:color .2s; text-wrap:balance; }
  .card .note { grid-column:1; font-size:14.5px; color:var(--muted); margin:0; }
  .card .stat { grid-column:2; grid-row:1 / span 3; text-align:right; display:grid; gap:2px; justify-items:end; }
  .card .stat b { font-weight:300; font-size:30px; line-height:1; font-variant-numeric:tabular-nums; }
  .card .stat small { font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
  .card .sizes { display:inline-flex; gap:4px; }
  .card .sizes span { font-size:11px; letter-spacing:.08em; padding:3px 7px; border:1px solid var(--line); border-radius:999px; color:var(--muted); }
  .card .sizes span.on { color:var(--fg); border-color:var(--dim); }
  .card .arrow { grid-column:2; grid-row:1 / span 3; color:var(--dim); font-size:22px; font-weight:300; }
  .empty { color:var(--muted); font-size:15px; padding:22px 0; border-top:1px solid var(--line); }
  footer { margin-top:auto; padding-top:16px; border-top:1px solid var(--orange); display:flex; align-items:baseline; gap:10px; }
  footer .mark { font-family:var(--font-mark); color:var(--orange); font-size:18px; letter-spacing:.04em; }
  footer .desc { color:var(--muted); font-size:13px; }
  .view { animation: fade .25s ease; }
  @keyframes fade { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
  @media (prefers-reduced-motion: reduce) { .view { animation:none; } }
</style>
</head>
<body>
<main class="page">
  <section class="hero">
    <p class="crumbs" id="crumbs"></p>
    <h1 id="h1">Rou<em>tes</em></h1>
    <p class="sub" id="sub">Walks from the front door, drawn on our own maps.</p>
  </section>
  <section class="view" id="view" aria-live="polite"></section>
  <footer>
    <span class="mark">DARIDEH</span>
    <span class="desc">routes</span>
  </footer>
</main>
<script>
(function () {
  var DATA = __DATA__;
  var view = document.getElementById('view'), h1 = document.getElementById('h1'), sub = document.getElementById('sub'), crumbs = document.getElementById('crumbs');
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function km(v) { return v.toFixed(1).replace('.', ','); }
  function dur(m) { var h = Math.floor(m / 60), r = m % 60; return h === 0 ? r + ' min' : (r === 0 ? h + ' h' : h + ' h ' + (r < 10 ? '0' : '') + r); }
  function sizes(routes) {
    var have = {}; routes.forEach(function (r) { have[r.size] = true; });
    return '<span class="sizes">' + ['S', 'M', 'L', 'XL'].map(function (s) { return '<span class="' + (have[s] ? 'on' : '') + '">' + s + '</span>'; }).join('') + '</span>';
  }
  function regionCard(r) {
    var n = 0; r.cats.forEach(function (c) { n += c.routes.length; });
    return '<a class="card" href="#' + r.slug + '"><span class="where">' + r.cats.length + ' categories · ' + n + ' walks</span><h2 class="title">' + esc(r.name) + '</h2><p class="note">' + esc(r.cue) + '</p><span class="arrow" aria-hidden="true">›</span></a>';
  }
  function catCard(r, c) {
    var one = c.routes.length === 1;
    var href = one ? c.routes[0].path : '#' + r.slug + '/' + c.slug;
    var kms = c.routes.map(function (x) { return x.km; });
    var range = one ? km(kms[0]) + ' km' : km(Math.min.apply(null, kms)) + ' to ' + km(Math.max.apply(null, kms)) + ' km';
    return '<a class="card" href="' + href + '"><span class="where">' + (one ? '1 walk' : c.routes.length + ' walks') + ' · ' + range + '</span><h2 class="title">' + esc(c.name) + '</h2><p class="note">' + esc(c.cue) + '</p><span class="stat">' + sizes(c.routes) + '</span></a>';
  }
  function routeCard(m) {
    return '<a class="card" href="' + m.path + '"><span class="where">' + m.size + ' · about ' + dur(m.min) + (m.draft ? ' · <span class="draft">draft</span>' : '') + '</span><h2 class="title">' + esc(m.title) + '</h2><p class="note">' + esc(m.card) + '</p><span class="stat"><b>' + km(m.km) + '</b><small>km</small></span></a>';
  }
  function render() {
    var parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
    var region = parts[0] && DATA.filter(function (r) { return r.slug === parts[0]; })[0];
    var cat = region && parts[1] && region.cats.filter(function (c) { return c.slug === parts[1]; })[0];
    var html = '', bc = '';
    if (!region) {
      h1.innerHTML = 'Rou<em>tes</em>'; sub.textContent = 'Walks from the front door, drawn on our own maps.';
      bc = '<b>Where</b>';
      html = '<p class="step">Pick a region</p><div class="list">' + DATA.map(regionCard).join('') + '</div>';
    } else if (!cat) {
      h1.innerHTML = esc(region.name).replace(/(.{3})$/, '<em>$1</em>'); sub.textContent = region.cue;
      bc = '<a href="#">Where</a><span class="sep">›</span><b>' + esc(region.name) + '</b>';
      html = '<p class="step">Pick a category <i>one walk opens straight away</i></p><div class="list">' + region.cats.map(function (c) { return catCard(region, c); }).join('') + '</div>';
    } else {
      h1.innerHTML = esc(cat.name).replace(/(\S+)$/, '<em>$1</em>'); sub.textContent = cat.cue;
      bc = '<a href="#">Where</a><span class="sep">›</span><a href="#' + region.slug + '">' + esc(region.name) + '</a><span class="sep">›</span><b>' + esc(cat.name) + '</b>';
      html = '<p class="step">Pick a walk <i>' + cat.routes.length + ' sizes</i></p><div class="list">' + cat.routes.map(routeCard).join('') + '</div>';
    }
    crumbs.innerHTML = bc;
    view.innerHTML = html;
    view.style.animation = 'none'; void view.offsetWidth; view.style.animation = '';
    document.title = cat ? cat.name + ' · ' + region.name + ' · Routes' : (region ? region.name + ' · Routes' : 'Routes');
  }
  window.addEventListener('hashchange', render);
  render();
})();
</script>
</body>
</html>
'''
page = page.replace("__DATA__", DATA)
open(os.path.join(ROOT, "index.html"), "w").write(page)
print("index: %d regions, %d routes" % (len(regions), len(metas)))
