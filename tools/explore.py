#!/usr/bin/env python3
"""Try candidate loops quickly: python3 -I tools/explore.py data.geojson.gz candidates.json [debug.png]
candidates.json: {"home": [lat, lon], "pois": {"name": [lat, lon]}, "loops": {"name": [[lat, lon], ...]}}
Prints length, surface mix and street sequence per loop; renders a debug image of the last loop with all POIs."""
import json, sys, math, os
sys.argv_saved = list(sys.argv)
cand = json.load(open(sys.argv[2]))
# reuse build.py's graph code by exec-ing its top part with a fake config
src = open(os.path.join(os.path.dirname(__file__), "build.py")).read()
head = src[:src.index("WP = CFG[\"waypoints\"]")]
CFG = {"home": {"lat": cand["home"][0], "lon": cand["home"][1]}, "data": sys.argv[1]}
ns = {"CFG": CFG, "__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "build.py")}
head = head.replace('CFG = json.load(open(sys.argv[1]))', '')
exec(head, ns)
nodes, adj, nearest, dijkstra, hav = ns["nodes"], ns["adj"], ns["nearest"], ns["dijkstra"], ns["hav"]
HOME = tuple(cand["home"])
def run(name, lls):
    ids = [nearest(*p) for p in [HOME] + lls]; ids.append(ids[0])
    tot = 2*hav(HOME, nodes[ids[0]]); by = {}; cums = [0]; names = []; allp = []
    for i in range(len(ids)-1):
        path, legs = dijkstra(ids[i], ids[i+1]); allp += path if not allp else path[1:]
        for L, (hw, nm, sf) in legs:
            tot += L; by[hw] = by.get(hw, 0) + L
            if nm and (not names or names[-1] != nm): names.append(nm)
        cums.append(round(tot))
    seen = {}; dup = 0
    for i, n in enumerate(allp):
        if n in seen and i - seen[n] > 1: dup += 1
        seen[n] = i
    unp = sum(v for k, v in by.items() if k in ("path", "track", "footway", "bridleway"))
    print("%s: %.1f km, unpaved %.1f km, major roads %.1f km, revisits %d" % (name, tot/1000, unp/1000, (by.get("secondary", 0)+by.get("primary", 0))/1000, dup))
    print("   legs:", cums); print("   streets:", " > ".join(names))
    return allp
last = None
for name, lls in cand["loops"].items(): last = run(name, lls)
if len(sys.argv) > 3 and last:
    import cairosvg
    pts = [nodes[n] for n in last] + [(v[0], v[1]) for v in cand["pois"].values()] + [HOME]
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    mlat, Mlat, mlon, Mlon = min(lats)-.004, max(lats)+.004, min(lons)-.006, max(lons)+.006
    K = math.cos(math.radians((mlat+Mlat)/2)); span = max((Mlon-mlon)*K, Mlat-mlat); SX = 1000/span
    def proj(lat, lon): return ((lon-mlon)*K*SX, (Mlat-lat)*SX)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1400" height="1400"><rect width="1000" height="1000" fill="#111"/>']
    css = {"park": "fill:#1a2a14;stroke:none", "rd ped": "fill:none;stroke:#6a6;stroke-width:.7;stroke-dasharray:2 2", "rd minor": "fill:none;stroke:#888;stroke-width:.8", "rd major": "fill:none;stroke:#ddd;stroke-width:1.6", "water": "fill:#123", "stream": "fill:none;stroke:#245;stroke-width:.5"}
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
    for e in ns["els"]:
        cls = classify(e.get("tags", {}))
        if not cls or cls == "rail": continue
        p = [proj(g["lat"], g["lon"]) for g in e["geometry"]]
        if not any(0 <= x <= 1000 and 0 <= y <= 1000 for x, y in p): continue
        svg.append('<path d="M%s%s" style="%s"/>' % ("L".join("%.1f,%.1f" % q for q in p), "Z" if cls in ("park", "water") else "", css.get(cls, "fill:none;stroke:#555")))
    svg.append('<path d="M%s" fill="none" stroke="#E85D1F" stroke-width="2"/>' % "L".join("%.1f,%.1f" % proj(*nodes[n]) for n in last))
    for name, v in cand["pois"].items():
        x, y = proj(v[0], v[1]); svg.append('<circle cx="%.1f" cy="%.1f" r="4" fill="#fff"/><text x="%.1f" y="%.1f" fill="#ff0" font-size="11">%s</text>' % (x, y, x+6, y-3, name))
    x, y = proj(*HOME); svg.append('<circle cx="%.1f" cy="%.1f" r="6" fill="none" stroke="#E85D1F" stroke-width="2"/>' % (x, y))
    for name, lls in [list(cand["loops"].items())[-1]]:
        for i, p in enumerate(lls):
            x, y = proj(*p); svg.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#4A8CFF"/><text x="%.1f" y="%.1f" fill="#4A8CFF" font-size="10">%d</text>' % (x, y, x+5, y+4, i+1))
    svg.append("</svg>")
    cairosvg.svg2png(bytestring="".join(svg).encode(), write_to=sys.argv[3]); print("debug image", sys.argv[3])
