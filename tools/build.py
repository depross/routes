#!/usr/bin/env python3
"""Build a route page from a JSON config and an OSM extract.

    python3 -I tools/build.py routes/nature-m.json

Config keys: slug, out (directory for index.html), data (gz GeoJSON or Overpass JSON),
title_html, ring, sub, cue, category, size, home {lat, lon}, waypoints [{name, lat, lon, label, map, dy,
title, note, accent, maps, addr}], extras [{name, lat, lon, anchor}], labels [street names],
goodtoknow [paragraphs], more [paragraphs], pace_kmh (default 4.4), private_radius_m (default 350),
pad (default .10), xbias/ybias (default .62/.36), simplify (default .6).
Writes <out>/index.html and <out>/check.png (rasterised map for a look).
"""
import json, math, sys, heapq, gzip, html, os, re

CFG = json.load(open(sys.argv[1]))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rel(p): return p if os.path.isabs(p) else os.path.join(ROOT, p)

PREFER = {"path": .55, "track": .6, "footway": .6, "bridleway": .6, "cycleway": .8,
          "living_street": .9, "residential": 1.0, "unclassified": 1.0, "service": 1.1,
          "tertiary": 1.3, "secondary": 1.8, "primary": 2.2, "trunk": 5, "pedestrian": .8, "steps": 1.0}
HOME = (CFG["home"]["lat"], CFG["home"]["lon"])
PRIV_R = CFG.get("private_radius_m", 350)

def hav(a, b):
    la1, lo1 = math.radians(a[0]), math.radians(a[1]); la2, lo2 = math.radians(b[0]), math.radians(b[1])
    x = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*6371000*math.asin(math.sqrt(x))

# ---------- load OSM ----------
src = rel(CFG["data"])
d = json.load(gzip.open(src, "rt") if src.endswith(".gz") else open(src))
if d.get("type") == "FeatureCollection":
    els = []
    for i, f in enumerate(d["features"]):
        g = f["geometry"]; t = f.get("properties", {})
        if g["type"] == "LineString":
            if not any(k in t for k in ("highway", "railway", "waterway")): continue
            rings = [g["coordinates"]]
        elif g["type"] == "Polygon": rings = g["coordinates"]
        elif g["type"] == "MultiPolygon": rings = [r for poly in g["coordinates"] for r in poly]
        else: continue
        for r in rings:
            els.append({"type": "way", "tags": t, "nodes": ["%.7f,%.7f" % (c[1], c[0]) for c in r],
                        "geometry": [{"lat": c[1], "lon": c[0]} for c in r]})
else:
    els = [e for e in d["elements"] if e["type"] == "way"]

# ---------- graph ----------
nodes = {}; adj = {}
for e in els:
    t = e.get("tags", {}); hw = t.get("highway")
    if not hw or hw not in PREFER: continue
    if t.get("foot") == "no": continue
    if t.get("access") in ("private", "no") and t.get("foot") not in ("yes", "designated", "permissive"):
        if min(hav(HOME, (g["lat"], g["lon"])) for g in e["geometry"]) > PRIV_R: continue
    nds = e["nodes"]; geo = e["geometry"]
    for i, nid in enumerate(nds): nodes[nid] = (geo[i]["lat"], geo[i]["lon"])
    for i in range(len(nds)-1):
        a, b = nds[i], nds[i+1]; L = hav(nodes[a], nodes[b]); c = L*PREFER[hw]
        info = (hw, t.get("name"), t.get("surface"))
        adj.setdefault(a, []).append((b, c, L, info)); adj.setdefault(b, []).append((a, c, L, info))

def _nearest(lat, lon):
    best, bd = None, 1e18
    for nid, p in nodes.items():
        if nid not in adj: continue
        dd = (p[0]-lat)**2 + ((p[1]-lon)*0.63)**2
        if dd < bd: bd, best = dd, nid
    return best
# extra links the data lacks (an unmapped field track, a gap in the network): straight edges between the nearest nodes
for a, b in CFG.get("links", []):
    na, nb = _nearest(a[0], a[1]), _nearest(b[0], b[1])
    L = hav(nodes[na], nodes[nb]); info = ("track", None, "unmapped")
    adj.setdefault(na, []).append((nb, L*PREFER["track"], L, info)); adj.setdefault(nb, []).append((na, L*PREFER["track"], L, info))
    print("link added: %.0f m" % L)

def nearest(lat, lon):
    best, bd = None, 1e18
    for nid, p in nodes.items():
        if nid not in adj: continue
        dd = (p[0]-lat)**2 + ((p[1]-lon)*0.63)**2
        if dd < bd: bd, best = dd, nid
    return best

def dijkstra(s, g):
    dist = {s: 0}; prev = {}; pq = [(0, s)]
    while pq:
        dc, u = heapq.heappop(pq)
        if u == g: break
        if dc > dist.get(u, 1e18): continue
        for v, c, L, info in adj.get(u, []):
            nd = dc + c
            if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = (u, L, info); heapq.heappush(pq, (nd, v))
    if g not in prev and g != s: raise SystemExit("no path to %s" % str(nodes[g]))
    path = [g]; legs = []
    while path[-1] != s:
        u, L, info = prev[path[-1]]; legs.append((L, info)); path.append(u)
    return path[::-1], legs[::-1]

WP = CFG["waypoints"]
wp_nodes = [nearest(w["lat"], w["lon"]) for w in WP]
nodes["__home__"] = HOME
conn = hav(HOME, nodes[wp_nodes[0]])
order = wp_nodes + [wp_nodes[0]]
route = ["__home__"]; cum = conn; segs = [(conn, ("connector", None, None))]; stop_cum = [0.0]
for i in range(len(order)-1):
    p, legs = dijkstra(order[i], order[i+1])
    if i > 0: p = p[1:]
    for L, info in legs: cum += L
    stop_cum.append(cum); route.extend(p); segs.extend(legs)
route.append("__home__"); cum += conn; total = cum
wp_nodes[0] = "__home__"
by = {}
for L, (hw, nm, sf) in segs: by[hw] = by.get(hw, 0) + L
unpaved = sum(v for k, v in by.items() if k in ("path", "track", "footway", "bridleway"))
print("total %.0f m (connector %.0f m), unpaved %.0f m" % (total, conn, unpaved)); print({k: round(v) for k, v in by.items()})
names = []
for L, (hw, nm, sf) in segs:
    if nm and (not names or names[-1] != nm): names.append(nm)
print("streets:", names)

# ---------- projection ----------
lats = [nodes[n][0] for n in route]; lons = [nodes[n][1] for n in route]
mlat, Mlat, mlon, Mlon = min(lats), max(lats), min(lons), max(lons)
K = math.cos(math.radians((mlat+Mlat)/2)); PAD = CFG.get("pad", .10)
w = (Mlon-mlon)*K; h = (Mlat-mlat); span = max(w, h)*(1+2*PAD); SX = 600/span
MINLON = mlon - ((span-w)*CFG.get("xbias", .62))/K; MAXLAT = Mlat + (span-h)*CFG.get("ybias", .36)
def proj(lat, lon): return ((lon-MINLON)*K*SX, (MAXLAT-lat)*SX)
print("proj:", {"MINLON": MINLON, "MAXLAT": MAXLAT, "K": K, "SX": SX, "m_per_px": 111320/SX})

def dp(pts, eps):
    if len(pts) < 3: return pts
    def pdist(p, a, b):
        ax, ay = a; bx, by_ = b; px, py = p; dx, dy = bx-ax, by_-ay
        if dx == dy == 0: return math.hypot(px-ax, py-ay)
        t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
        return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
    mx, idx = 0, 0
    for i in range(1, len(pts)-1):
        dd = pdist(pts[i], pts[0], pts[-1])
        if dd > mx: mx, idx = dd, i
    return dp(pts[:idx+1], eps)[:-1] + dp(pts[idx:], eps) if mx > eps else [pts[0], pts[-1]]
def fmt(pts, close=False): return "M" + "L".join("%.1f,%.1f" % p for p in pts) + ("Z" if close else "")

def classify(t):
    hw = t.get("highway")
    if hw in ("primary", "secondary", "trunk", "primary_link", "secondary_link"): return "rd major"
    if hw in ("tertiary", "residential", "unclassified", "living_street", "tertiary_link", "service"): return "rd minor"
    if hw in ("path", "track", "footway", "bridleway", "cycleway", "pedestrian", "steps"): return "rd ped"
    if t.get("railway") == "rail": return "rail"
    if t.get("natural") == "water" or t.get("waterway") in ("river", "canal"): return "water"
    if t.get("waterway") in ("stream", "ditch"): return "stream"
    if t.get("natural") == "wood" or t.get("landuse") in ("forest", "wood") or t.get("leisure") in ("park", "nature_reserve"): return "park"
    return None

EPS = CFG.get("simplify", .6)
groups = {}; named = {}
for e in els:
    t = e.get("tags", {}); cls = classify(t)
    if not cls: continue
    pts = [proj(g["lat"], g["lon"]) for g in e["geometry"]]
    if not any(-320 <= x <= 920 and -320 <= y <= 920 for x, y in pts): continue
    pts = [(round(x, 1), round(y, 1)) for x, y in pts]
    if cls.startswith("rd") or cls in ("rail", "stream"):
        pts = [p for p in pts if -320 <= p[0] <= 920 and -320 <= p[1] <= 920]
    if len(pts) < 2: continue
    pts = dp(pts, EPS)
    closed = cls in ("park", "water") and e["nodes"][0] == e["nodes"][-1]
    groups[cls] = groups.get(cls, "") + fmt(pts, closed)
    if t.get("name") and cls.startswith("rd"): named.setdefault(t["name"], []).append(pts)

rpts = dp([(round(x, 1), round(y, 1)) for x, y in (proj(*nodes[n]) for n in route)], .8)
ROUTE_D = fmt(rpts)

# ---------- SVG ----------
def esc(s): return html.escape(str(s), quote=True)
order_cls = ["park", "water", "stream", "rail", "rd ped", "rd minor", "rd major"]
cls_name = {"park": "park", "water": "water", "stream": "water stream", "rail": "rail", "rd ped": "rd ped", "rd minor": "rd minor", "rd major": "rd major"}
streets = "".join('<path class="%s" vector-effect="non-scaling-stroke" d="%s"/>' % (cls_name[k], groups[k]) for k in order_cls if k in groups)

def seglen(pts): return sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
labels = []
for i, name in enumerate(CFG.get("labels", [])):
    best = None
    for pts in named.get(name, []):
        pts = [p for p in pts if 10 <= p[0] <= 590 and 10 <= p[1] <= 590]
        if len(pts) >= 2 and (best is None or seglen(pts) > seglen(best)): best = pts
    if not best or seglen(best) < 60: continue
    if best[-1][0] < best[0][0]: best = best[::-1]
    out = []
    for j, (x, y) in enumerate(best):
        a = best[min(j+1, len(best)-1)]; b = best[max(j-1, 0)]; dx, dy = a[0]-b[0], a[1]-b[1]; L = math.hypot(dx, dy) or 1
        out.append((x + 2.5*dy/L, y - 2.5*dx/L))
    labels.append('<path id="sn%d" d="%s" fill="none"/><text class="sn"><textPath href="#sn%d" startOffset="50%%" text-anchor="middle">%s</textPath></text>' % (i, fmt(out), i, esc(name)))

stops = []
for i, wdef in enumerate(WP):
    s = dict(wdef); s["px"] = proj(*nodes[wp_nodes[i]]); s["cum_m"] = stop_cum[i]; stops.append(s)
pts_svg = []
def ptg(cls, x, y, inner, data=""):
    # translate to the point, then a counter-scaled inner group so markers and labels keep their screen size when zooming
    return '<g class="pt %s" transform="translate(%.1f,%.1f)"%s><g class="pz">%s</g></g>' % (cls, x, y, data, inner)
for s in stops[1:]:
    if not s.get("map", True): continue
    x, y = s["px"]; anchor = s.get("anchor") or ("start" if x < 420 else "end"); dx = 8 if anchor == "start" else -8
    pts_svg.append(ptg("", x, y, '<circle r="4"/><text class="ml" x="%.1f" y="%.1f" text-anchor="%s">%s</text>' % (dx, 4+s.get("dy", 0), anchor, esc(s.get("label", s["name"])))))
hx, hy = stops[0]["px"]; hanchor = stops[0].get("anchor") or ("start" if hx < 400 else "end")
pts_svg.append(ptg("home", hx, hy, '<circle r="9"/><circle r="3" class="core"/><text class="ml home" x="%.1f" y="4" text-anchor="%s">Home</text>' % ((14 if hanchor == "start" else -14), hanchor)))
for c in CFG.get("extras", []):
    x, y = proj(c["lat"], c["lon"])
    if not (-250 < x < 850 and -250 < y < 850): continue
    anchor = c.get("anchor", "start"); dx = 8 if anchor == "start" else -8
    pts_svg.append(ptg("cafe", x, y, '<circle r="3.2"/><text class="ml dim" x="%.1f" y="%.1f" text-anchor="%s">%s</text>' % (dx, 3.5+c.get("dy", 0), anchor, esc(c["name"]))))

M = 320
scale_m = 500 if 111320/SX < 12 else 1000
scale_px = scale_m/111320*SX
svg = f'''<svg class="map has-streets" id="mapsvg" viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(CFG.get("aria", "Map of the walk"))}" data-scale-px="{scale_px:.2f}" data-scale-m="{scale_m}">
  <defs>
    <pattern id="dots" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#2A2724"/></pattern>
  </defs>
  <rect x="-{M}" y="-{M}" width="{600+2*M}" height="{600+2*M}" fill="url(#dots)"/>
  <g class="streets">
  {streets}
  {"".join(labels)}
  </g>
  <path class="rt glow" vector-effect="non-scaling-stroke" d="{ROUTE_D}"/>
  <path class="rt walk" vector-effect="non-scaling-stroke" d="{ROUTE_D}"/>
  <g class="pts">{"".join(pts_svg)}</g>
  <g class="me" id="me" hidden><g class="pz"><circle class="me-halo" r="14"/><circle class="me-acc" r="0"/><circle class="me-dot" r="4.5"/></g></g>
</svg>'''


# ---------- hero icon per category (line art in the page's own strokes) ----------
ICON_ALT = {"Nature": "A path leading into a small wood", "History": "A row of headstones with a path between the fields",
            "City": "Three church towers and a path into town", "Beer & hops": "Hop bines on their poles", "Border": "A post mill on the hill, a path climbing to it"}
ICONS = {
"Nature": '''<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path class="ground" d="M8,92 Q60,84 112,92"/>
          <path class="path" d="M58,112 C62,96 48,88 56,74 C62,64 70,60 72,52"/>
          <g class="tree">
            <path d="M34,78 L34,54"/><path d="M34,54 C22,54 18,40 28,34 C26,24 40,20 44,28 C54,26 56,42 46,46 C50,56 40,58 34,54 Z"/>
            <path d="M86,80 L86,50"/><path d="M86,50 C72,52 68,34 80,30 C80,16 100,16 100,30 C110,36 104,52 92,50 C92,54 88,54 86,50 Z"/>
            <path d="M62,56 L62,44"/><path d="M62,44 C56,44 54,36 59,34 C58,28 66,26 68,30 C74,30 74,40 68,42 C70,46 65,47 62,44 Z"/>
          </g>
        </svg>''',
"History": '''<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path class="ground" d="M6,84 Q60,78 114,84"/>
          <path class="path" d="M60,112 C58,100 62,94 60,86"/>
          <g class="tree">
            <path d="M20,82 L20,56 Q20,48 28,48 Q36,48 36,56 L36,82"/>
            <path d="M44,82 L44,52 Q44,44 52,44 Q60,44 60,52 L60,82"/>
            <path d="M68,82 L68,56 Q68,48 76,48 Q84,48 84,56 L84,82"/>
            <path d="M92,82 L92,60 Q92,52 100,52 Q108,52 108,60 L108,82"/>
            <path d="M52,54 L52,66 M47,59 L57,59"/>
            <path d="M28,58 L28,66"/><path d="M76,58 L76,66"/><path d="M100,62 L100,68"/>
          </g>
          <path class="tree" d="M60,28 C58,34 62,38 60,44"/>
          <g fill="#E85D1F"><circle cx="55" cy="21" r="5"/><circle cx="65" cy="21" r="5"/><circle cx="60" cy="15.5" r="5"/><circle cx="60" cy="26" r="5"/></g>
          <circle cx="60" cy="21" r="2.2" fill="#000"/>
        </svg>''',
"City": '''<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path class="ground" d="M6,88 Q60,82 114,88"/>
          <path class="path" d="M60,112 C64,100 54,96 58,86"/>
          <g class="tree">
            <path d="M22,86 L22,52 L30,40 L38,52 L38,86"/><path d="M30,40 L30,30"/><path d="M26,62 L34,62"/>
            <path d="M50,86 L50,36 L60,18 L70,36 L70,86"/><path d="M60,18 L60,8"/><path d="M55,48 Q60,42 65,48"/><path d="M55,64 L65,64"/>
            <path d="M82,86 L82,56 L90,46 L98,56 L98,86"/><path d="M90,46 L90,38"/><path d="M86,66 L94,66"/>
            <path d="M38,86 L50,86 M70,86 L82,86"/>
          </g>
        </svg>''',
"Beer & hops": '''<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path class="ground" d="M6,96 Q60,90 114,96"/>
          <path class="path" d="M60,112 C62,104 58,100 60,94"/>
          <g class="tree">
            <path d="M30,94 L30,16"/><path d="M60,94 L60,10"/><path d="M90,94 L90,16"/>
            <path d="M30,16 L60,10 L90,16" stroke-dasharray="2 2"/>
            <path d="M30,90 C40,78 24,70 32,58 C40,46 26,40 32,26"/>
            <path d="M60,88 C70,76 52,68 60,54 C68,42 52,34 60,20"/>
            <path d="M90,90 C100,78 84,70 92,58 C100,46 86,40 92,26"/>
          </g>
          <g fill="none" stroke="#E85D1F" stroke-width="1.2" stroke-linejoin="round">
            <path d="M38,44 l5,-4 l5,4 l-1,7 l-4,4 l-4,-4 z"/>
            <path d="M68,38 l5,-4 l5,4 l-1,7 l-4,4 l-4,-4 z"/>
            <path d="M96,52 l5,-4 l5,4 l-1,7 l-4,4 l-4,-4 z"/>
          </g>
        </svg>''',
"Border": '''<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path class="ground" d="M6,96 Q40,60 70,66 Q100,72 114,96"/>
          <path class="path" d="M20,112 C30,100 36,92 48,84 C56,78 62,74 68,70"/>
          <g class="tree">
            <path d="M72,70 L70,46 L82,44 L84,68 Z"/>
            <path d="M74,72 L70,78 M82,70 L86,78"/>
            <path d="M76,45 L76,38"/>
            <path d="M76,38 L96,20 M76,38 L58,20 M76,38 L94,56 M76,38 L58,56"/>
            <path d="M76,38 L92,24 L96,20 M76,38 L62,24 L58,20"/>
          </g>
          <path d="M28,92 L28,76 M24,76 L32,76 M24,80 L32,80" fill="none" stroke="#E85D1F" stroke-width="1.2" stroke-linecap="round"/>
        </svg>''',
}

# ---------- page ----------
def kmf(m): return ("%.1f km" % (m/1000)).replace(".", ",")
km_s = ("%.1f" % (total/1000)).replace(".", ",")
mins = round(total/1000/CFG.get("pace_kmh", 4.4)*60/5)*5
def dur(m):
    h, r = divmod(m, 60)
    if h == 0: return "%d min" % r
    if r == 0: return "%d h" % h
    return "%d h %02d" % (h, r)

def stop_html(s):
    where = ""
    if s.get("maps"):
        where = '<p class="where"><span>%s</span><a href="%s" target="_blank" rel="noopener">Open in Maps</a></p>' % (esc(s.get("addr", "")), esc(s["maps"]))
    more = ('<details class="more"><summary>More</summary><div class="more-body">%s</div></details>' % "".join("<p>%s</p>" % m for m in s["more"])) if s.get("more") else ""
    accent = ('<p class="accent">%s</p>' % s["accent"]) if s.get("accent") else ""
    return f'''    <article class="stop" data-km="{s["cum_m"]/1000:.3f}">
      <span class="dot"></span>
      <div class="time">{kmf(s["cum_m"])}</div>
      <h3 class="title">{s["title"]}</h3>
      <p class="note">{s["note"]}</p>
      {accent}{where}{more}
    </article>'''
finish = dict(cum_m=total, title="Home", note="Boots off. %s in all, %s of it unpaved." % (kmf(total), kmf(unpaved)),
              accent=CFG.get("finish_accent", "About %s at a walking pace, longer if you stop." % dur(mins)))
STOPS_HTML = "\n".join(stop_html(s) for s in [s for s in stops if s.get("title")] + [finish])

tpl = open(os.path.join(ROOT, "tools", "template.html")).read()
G = "https://www.google.com/maps/search/?api=1&query="
rep = {
    "{{SVG}}": svg, "{{KM}}": km_s, "{{MIN}}": str(mins), "{{DUR}}": dur(mins), "{{STOPS}}": STOPS_HTML,
    "{{MINLON}}": repr(MINLON), "{{MAXLAT}}": repr(MAXLAT), "{{K}}": repr(K), "{{SX}}": repr(SX),
    "{{HLAT}}": repr(HOME[0]), "{{HLON}}": repr(HOME[1]),
    "{{TITLE}}": CFG["title"], "{{TITLE_HTML}}": CFG.get("title_html", CFG["title"]), "{{RING}}": CFG["ring"],
    "{{SUB}}": CFG["sub"], "{{CUE}}": CFG.get("cue", "Real streets, drawn to scale. The dashed line is the walk."),
    "{{TLCUE}}": CFG.get("tlcue", "Clockwise. Distances are from the front door."),
    "{{CATEGORY}}": CFG["category"], "{{SIZE}}": CFG["size"], "{{DESC}}": CFG.get("desc", ""),
    "{{GOODTOKNOW}}": "".join('<p%s>%s</p>' % (' class="soft"' if i else "", p) for i, p in enumerate(CFG.get("goodtoknow", []))),
    "{{MORE}}": ('<details class="more"><summary>More</summary><div class="more-body">%s</div></details>' % "".join("<p>%s</p>" % p for p in CFG["more"])) if CFG.get("more") else "",
    "{{ICON}}": ICONS.get(CFG["category"], ICONS["Nature"]), "{{ICON_ALT}}": ICON_ALT.get(CFG["category"], "Illustration"),
    "{{UP}}": CFG.get("up", "../../#%s/%s" % (CFG.get("region_slug", "poperinge"), CFG["category"].lower().replace(" & ", "-").replace(" ", "-"))), "{{ALL}}": "../../#" + CFG.get("region_slug", "poperinge"), "{{KEY}}": CFG["slug"],
}
page = tpl
for _ in range(2):
    for k, v in rep.items(): page = page.replace(k, v)
left = re.findall(r"\{\{[A-Z_]+\}\}", page)
assert not left, left
outdir = rel(CFG["out"]); os.makedirs(outdir, exist_ok=True)
open(os.path.join(outdir, "index.html"), "w").write(page)
json.dump({"slug": CFG["slug"], "path": CFG["out"].strip("/") + "/", "region": CFG.get("region", "Poperinge"), "region_slug": CFG.get("region_slug", "poperinge"),
           "category": CFG["category"], "size": CFG["size"], "title": CFG["title"], "card": CFG.get("card", CFG["sub"]),
           "km": round(total/1000, 1), "min": mins, "unpaved_km": round(unpaved/1000, 1), "draft": bool(CFG.get("draft"))},
          open(os.path.join(outdir, "meta.json"), "w"), ensure_ascii=False, indent=1)
print("wrote", os.path.join(outdir, "index.html"), len(page), "bytes;", km_s, "km", mins, "min")

# check image
try:
    import cairosvg
    rules = "\n".join(l for l in tpl.splitlines() if (l.strip().startswith(".map .") or l.strip().startswith(".map.has")) and "--k" not in l and "vector-effect" not in l)
    for k_, v_ in {"--bg": "#000000", "--fg": "#EDE8E1", "--muted": "#A8A197", "--dim": "#7C756D", "--line": "#2A2724", "--orange": "#E85D1F", "--now": "#4A8CFF", "--font-body": "sans-serif", "--font-accent": "serif"}.items():
        rules = rules.replace("var(%s)" % k_, v_)
    rules = rules.replace(".map .", "svg .").replace(".map.has-streets", "svg").replace("filter: drop-shadow(0 0 6px rgba(232,93,31,.7));", "")
    chk = svg.replace("<defs>", "<style>%s</style><defs>" % rules, 1).replace('fill="url(#dots)"/>', 'fill="#060505"/>', 1)
    chk = chk.replace(" hidden>", ' display="none">').replace("&", "&amp;")
    cairosvg.svg2png(bytestring=chk.encode(), write_to=os.path.join(outdir, "check.png"), output_width=1200, output_height=1200)
    print("check image written")
except Exception as ex:
    print("no check image:", ex)
