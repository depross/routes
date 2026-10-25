#!/usr/bin/env python3
"""Build route + street SVG from an Overpass JSON dump.

Usage: python3 -I build_map.py osm.json out.json
Outputs a JSON with: projection constants, street path strings per class,
named street segments, route points (px), route distance, stop pixel positions.
Waypoints are configured below.
"""
import json, math, sys, heapq

OSM = sys.argv[1]
OUT = sys.argv[2]

# ---- waypoints (lat, lon) in walking order, loop closes back to the first ----
WAYPOINTS = [
    ("Kleine Dasdreef 8", 50.846221, 2.688050),
    ("Helleketelweg", 50.850274, 2.691473),
    ("West along Helleketelweg", 50.848597, 2.677466),
    ("Helleketelweg south", 50.841734, 2.671187),
    ("Into the wood", 50.838341, 2.668510),
    ("Helleketelbos", 50.837264, 2.672060),
    ("Out of the wood", 50.838952, 2.674366),
    ("Vijfgemetenstraat", 50.840446, 2.678533),
    ("Kleine Casseldreef", 50.843663, 2.690802),
]
PREFER = {"path": .55, "track": .6, "footway": .6, "bridleway": .6, "cycleway": .8,
          "living_street": .9, "residential": 1.0, "unclassified": 1.0, "service": 1.1,
          "tertiary": 1.3, "secondary": 1.8, "primary": 2.2, "trunk": 5, "pedestrian": .8, "steps": 1.0}

import gzip
d = json.load(gzip.open(OSM, "rt") if OSM.endswith(".gz") else open(OSM))
if d.get("type") == "FeatureCollection":
    # osmium GeoJSON export: rebuild Overpass-style way elements, node ids keyed by coordinates
    els = []
    for i, f in enumerate(d["features"]):
        g = f["geometry"]; t = f.get("properties", {})
        rings = []
        if g["type"] == "LineString":
            if not any(k in t for k in ("highway", "railway", "waterway")): continue
            rings = [g["coordinates"]]
        elif g["type"] == "Polygon": rings = g["coordinates"]
        elif g["type"] == "MultiPolygon": rings = [r for poly in g["coordinates"] for r in poly]
        else: continue
        for r in rings:
            els.append({"type": "way", "id": i, "tags": t,
                        "nodes": ["%.7f,%.7f" % (c[1], c[0]) for c in r],
                        "geometry": [{"lat": c[1], "lon": c[0]} for c in r]})
else:
    els = d["elements"]

def hav(a, b):
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    x = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*6371000*math.asin(math.sqrt(x))

# ---- graph ----
nodes = {}   # id -> (lat, lon)
adj = {}     # id -> list of (nid, cost, length, wayinfo)
ways = []
for e in els:
    if e["type"] != "way": continue
    t = e.get("tags", {})
    ways.append(e)
    hw = t.get("highway")
    if not hw or hw not in PREFER: continue
    if t.get("access") in ("private", "no") and t.get("foot") not in ("yes", "designated", "permissive"):
        # private lanes are only usable when they are the walker's own driveway: within 350 m of home
        home = (WAYPOINTS[0][1], WAYPOINTS[0][2])
        if min(hav(home, (g["lat"], g["lon"])) for g in e["geometry"]) > 350: continue
    if t.get("foot") == "no": continue
    nds = e["nodes"]; geo = e["geometry"]
    for i, nid in enumerate(nds):
        nodes[nid] = (geo[i]["lat"], geo[i]["lon"])
    for i in range(len(nds)-1):
        a, b = nds[i], nds[i+1]
        L = hav(nodes[a], nodes[b])
        c = L * PREFER[hw]
        info = (hw, t.get("name"), t.get("surface"))
        adj.setdefault(a, []).append((b, c, L, info))
        adj.setdefault(b, []).append((a, c, L, info))

def nearest(lat, lon):
    best, bd = None, 1e18
    for nid, p in nodes.items():
        if nid not in adj: continue
        dd = (p[0]-lat)**2 + ((p[1]-lon)*0.63)**2
        if dd < bd: bd, best = dd, nid
    return best

def dijkstra(s, g):
    dist = {s: 0}; prev = {}
    pq = [(0, s)]
    while pq:
        dc, u = heapq.heappop(pq)
        if u == g: break
        if dc > dist.get(u, 1e18): continue
        for v, c, L, info in adj.get(u, []):
            nd = dc + c
            if nd < dist.get(v, 1e18):
                dist[v] = nd; prev[v] = (u, L, info); heapq.heappush(pq, (nd, v))
    path = [g]; legs = []
    while path[-1] != s:
        u, L, info = prev[path[-1]]
        legs.append((L, info)); path.append(u)
    return path[::-1], legs[::-1]

wp_nodes = [nearest(la, lo) for _, la, lo in WAYPOINTS]
HOME_LL = (WAYPOINTS[0][1], WAYPOINTS[0][2])
nodes["__home__"] = HOME_LL
conn = hav(HOME_LL, nodes[wp_nodes[0]])
print("connector to network: %.0f m" % conn)
route = []; segs = []; cum = 0.0; stops_px = []
order = wp_nodes + [wp_nodes[0]]
stop_cum = [0.0]
route = ["__home__"]; cum = conn; segs.append((conn, ("connector", None, None)))
for i in range(len(order)-1):
    p, legs = dijkstra(order[i], order[i+1])
    if i > 0: p = p[1:]
    for (L, info) in legs:
        cum += L
    stop_cum.append(cum)
    route.extend(p)
    segs.extend(legs)
route.append("__home__"); cum += conn; segs.append((conn, ("connector", None, None)))
total = cum
wp_nodes[0] = "__home__"

# surface summary
by = {}
for L, (hw, name, surf) in segs:
    by[hw] = by.get(hw, 0) + L
names_used = []
for L, (hw, name, surf) in segs:
    if name and (not names_used or names_used[-1] != name): names_used.append(name)

# ---- projection: fit the route with a margin on a 600x600 canvas ----
lats = [nodes[n][0] for n in route]; lons = [nodes[n][1] for n in route]
mlat, Mlat, mlon, Mlon = min(lats), max(lats), min(lons), max(lons)
lat0 = (mlat+Mlat)/2; K = math.cos(math.radians(lat0))
PAD = 0.10
w = (Mlon-mlon)*K; h = (Mlat-mlat)
span = max(w, h) * (1+2*PAD)
SX = 600/span
MINLON = mlon - ((span - w)*0.62)/K
MAXLAT = Mlat + (span - h)*0.36
def proj(lat, lon):
    return ((lon-MINLON)*K*SX, (MAXLAT-lat)*SX)

def dp(pts, eps):
    if len(pts) < 3: return pts
    def pdist(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        dx, dy = bx-ax, by-ay
        if dx == dy == 0: return math.hypot(px-ax, py-ay)
        t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
        return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
    mx, idx = 0, 0
    for i in range(1, len(pts)-1):
        dd = pdist(pts[i], pts[0], pts[-1])
        if dd > mx: mx, idx = dd, i
    if mx > eps:
        return dp(pts[:idx+1], eps)[:-1] + dp(pts[idx:], eps)
    return [pts[0], pts[-1]]

def fmt(pts, close=False):
    s = "M" + "L".join("%.1f,%.1f" % p for p in pts)
    return s + ("Z" if close else "")

def classify(t):
    hw = t.get("highway")
    if hw in ("primary", "secondary", "trunk", "primary_link", "secondary_link"): return "rd major"
    if hw in ("tertiary", "residential", "unclassified", "living_street", "tertiary_link"): return "rd minor"
    if hw in ("service",): return "rd minor"
    if hw in ("path", "track", "footway", "bridleway", "cycleway", "pedestrian", "steps"): return "rd ped"
    if t.get("railway") == "rail": return "rail"
    if t.get("natural") == "water" or t.get("waterway") in ("river", "canal"): return "water"
    if t.get("waterway") in ("stream", "ditch"): return "stream"
    if t.get("natural") in ("wood",) or t.get("landuse") in ("forest", "wood") or t.get("leisure") in ("park", "nature_reserve"): return "park"
    return None

groups = {}
named = {}
for e in ways:
    t = e.get("tags", {})
    cls = classify(t)
    if not cls: continue
    pts = [proj(g["lat"], g["lon"]) for g in e["geometry"]]
    pts = [(round(x, 1), round(y, 1)) for x, y in pts if -40 <= x <= 640 and -40 <= y <= 640] if cls != "park" else [(round(x,1), round(y,1)) for x,y in pts]
    if len(pts) < 2: continue
    pts = dp(pts, 0.6)
    closed = cls in ("park", "water") and e["nodes"][0] == e["nodes"][-1]
    groups[cls] = groups.get(cls, "") + fmt(pts, closed)
    if t.get("name") and cls.startswith("rd"):
        named.setdefault(t["name"], []).append(pts)

rpts = [proj(*nodes[n]) for n in route]
rpts = dp([(round(x,1), round(y,1)) for x,y in rpts], 0.8)

out = {
    "proj": {"MINLON": MINLON, "MAXLAT": MAXLAT, "K": K, "SX": SX},
    "groups": groups, "named": named,
    "route": fmt(rpts), "route_pts": rpts,
    "total_m": total, "by_type": by, "names": names_used,
    "stops": [{"name": WAYPOINTS[i][0], "px": proj(*nodes[wp_nodes[i]]), "latlon": nodes[wp_nodes[i]], "cum_m": stop_cum[i]} for i in range(len(WAYPOINTS))],
    "bbox": [mlat, mlon, Mlat, Mlon],
}
json.dump(out, open(OUT, "w"))
print("total %.0f m" % total)
print({k: round(v) for k, v in by.items()})
print("streets:", names_used)
print("stops:", [(s["name"], round(s["cum_m"])) for s in out["stops"]])
print("proj:", out["proj"])
