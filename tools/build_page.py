#!/usr/bin/env python3
"""Assemble helleketelbos/index.html from map.json (output of build_map.py)."""
import json, math, sys, html

MAP = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
P = MAP["proj"]
SX = P["SX"]

def esc(s): return html.escape(s, quote=True)

# ---------- street layers ----------
order = ["park", "water", "stream", "rail", "rd ped", "rd minor", "rd major"]
cls_map = {"park": "park", "water": "water", "stream": "water stream", "rail": "rail",
           "rd ped": "rd ped", "rd minor": "rd minor", "rd major": "rd major"}
streets = []
for k in order:
    if k in MAP["groups"]:
        streets.append('<path class="%s" d="%s"/>' % (cls_map[k], MAP["groups"][k]))

# ---------- street labels along the longest in-canvas segment ----------
LABEL = ["Kleine Dasdreef", "Helleketelweg", "Vijfgemetenstraat", "Kleine Casseldreef", "Stoppelweg",
         "Boudeweelstraat", "Karel Grimminckweg", "Abeelseweg", "Vuileseulestraat", "Wulfhullestraat"]
def seglen(pts):
    return sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
labels = []
for i, name in enumerate(LABEL):
    segs = MAP["named"].get(name)
    if not segs: continue
    # merge all segments, pick the longest polyline inside the canvas
    best = None
    for pts in segs:
        pts = [p for p in pts if 10 <= p[0] <= 590 and 10 <= p[1] <= 590]
        if len(pts) >= 2 and (best is None or seglen(pts) > seglen(best)): best = pts
    if not best or seglen(best) < 60: continue
    if best[-1][0] < best[0][0]: best = best[::-1]
    # offset 2.5px "above" (perpendicular)
    out = []
    for j, (x, y) in enumerate(best):
        a = best[min(j+1, len(best)-1)]; b = best[max(j-1, 0)]
        dx, dy = a[0]-b[0], a[1]-b[1]; L = math.hypot(dx, dy) or 1
        out.append((x + 2.5*dy/L, y - 2.5*dx/L))
    d = "M" + "L".join("%.1f,%.1f" % p for p in out)
    labels.append('<path id="sn%d" d="%s" fill="none"/><text class="sn"><textPath href="#sn%d" startOffset="50%%" text-anchor="middle">%s</textPath></text>' % (i, d, i, esc(name)))

# ---------- stops ----------
G = lambda q: "https://www.google.com/maps/search/?api=1&query=" + q
COPY = {
  "Kleine Dasdreef 8": dict(label="Kleine Dasdreef 8", map=True, title="Out of the door", note="Down the gravel lane to Kleine Dasdreef, then left, up the dreef towards Helleketelweg. Quiet lanes; the odd tractor is the traffic.", accent="Clockwise, so the wood comes halfway and the long straight lanes are behind you on the way home."),
  "Helleketelweg": dict(label="", map=False, title="Left onto Helleketelweg", note="Follow it west. Open fields on both sides, hop poles in the distance, the first farms after about a kilometre."),
  "West along Helleketelweg": dict(label="Helleketelweg", map=True, dy=-8, title="Keep left, stay on Helleketelweg", note="At the junction with Karel Grimminckweg the road bends south. Stay on Helleketelweg; it runs straight at the wood from here.", accent="The wood is the dark line ahead."),
  "Helleketelweg south": dict(label="", map=False, title="Wood on your left", note="The forest edge now runs alongside the lane. Keep following the asphalt along the edge of the wood, down to the bottom corner."),
  "Into the wood": dict(label="Into the wood", map=True, title="Leave the asphalt", note="At the corner where the lane bends away, take the track into Helleketelbos. From here on it is unpaved: packed earth, roots, a boardwalk where it stays wet.", accent="White-and-red GR 5A marks and knooppunt signs along the way."),
  "Helleketelbos": dict(label="Helleketelbos", map=True, dy=10, title="Through the wood", note="East along the path through the heart of the wood. Oaks, sheep in the open parts, a chance of roe deer if you are early. The path then swings north and climbs gently out towards the lane.", accent="For a drink, De Boshoeve and the car park are a few hundred metres south of here, and Boskafé Boule Carré just beyond on Stoppelweg.", maps=G("Helleketelbos+Vijfgemetenstraat+4+Poperinge"), addr="Helleketelbos, Vijfgemetenstraat"),
  "Out of the wood": dict(label="Out of the wood", map=True, title="Back onto a lane", note="The path comes out on Vijfgemetenstraat at the top corner of the wood. Turn left; the lane heads north-east."),
  "Vijfgemetenstraat": dict(label="Vijfgemetenstraat", map=True, dy=-8, title="Right onto Kleine Casseldreef", note="A long, straight lane between the fields, pointing almost exactly at home. The wood falls away behind you.", accent="The longest stretch of the walk, a bit under a kilometre of straight line."),
  "Kleine Casseldreef": dict(label="Kleine Casseldreef", map=True, title="Left, and up the dreef", note="Where Kleine Casseldreef meets Kleine Dasdreef, turn left up the dreef, then left again into the gravel lane for the last stretch to the door."),
}
stops = []
for s_ in MAP["stops"]:
    c = COPY.get(s_["name"], {})
    s_ = dict(s_, **c)
    stops.append(s_)
stop_copy = list(stops) + [dict(name="Home", cum_m=MAP["total_m"], title="Home", note="Boots off. %s in all." % (("%.1f km" % (MAP["total_m"]/1000)).replace(".", ",")), accent="About %s at a walking pace, longer if the wood holds you up." % ("an hour and a half" if MAP["total_m"] > 6000 else "an hour and a quarter"))]
MAP["stop_copy"] = stop_copy
# optional extra markers (dim)
def projll(lat, lon): return ((lon-P["MINLON"])*P["K"]*SX, (P["MAXLAT"]-lat)*SX)
MAP["extras"] = []
for name, lat, lon, anchor in [("De Boshoeve · P", 50.8361274, 2.6708963, "start")]:
    x, y = projll(lat, lon)
    if 15 < x < 585 and 15 < y < 585: MAP["extras"].append({"name": name, "px": (x, y), "anchor": anchor})

def px(s): return s["px"]
home = stops[0]
pt_svg = []
# label side: start on the right unless near the right edge
side = {}
for s in stops[1:]:
    if not s.get("map"): continue
    x, y = px(s)
    anchor = "start" if x < 420 else "end"
    dx = 8 if anchor == "start" else -8
    label = s.get("label", s["name"])
    pt_svg.append('<g class="pt"><circle cx="%.1f" cy="%.1f" r="4"/><text class="ml" x="%.1f" y="%.1f" text-anchor="%s">%s</text></g>'
                  % (x, y, x+dx, y+4+s.get("dy", 0), anchor, esc(label)))
hx, hy = px(home)
hanchor = "start" if hx < 400 else "end"
pt_svg.append('<g class="pt home"><circle cx="%.1f" cy="%.1f" r="9"/><circle cx="%.1f" cy="%.1f" r="3" class="core"/><text class="ml home" x="%.1f" y="%.1f" text-anchor="%s">%s</text></g>'
              % (hx, hy, hx, hy, hx + (14 if hanchor == "start" else -14), hy+4, hanchor, esc("Home")))
# optional café marker
for c in MAP.get("extras", []):
    x, y = c["px"]
    anchor = c.get("anchor", "start"); dx = 8 if anchor == "start" else -8
    pt_svg.append('<g class="pt cafe"><circle cx="%.1f" cy="%.1f" r="3.2"/><text class="ml dim" x="%.1f" y="%.1f" text-anchor="%s">%s</text></g>' % (x, y, x+dx, y+3.5, anchor, esc(c["name"])))

scale_px = 500/111320*SX
svg = f'''<svg class="map has-streets" id="mapsvg" viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Map of the Helleketelbos loop from Kleine Dasdreef">
  <defs>
    <clipPath id="canvas"><rect width="600" height="600"/></clipPath>
    <pattern id="dots" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#2A2724"/></pattern>
  </defs>
  <rect width="600" height="600" fill="url(#dots)"/>
  <g class="streets" clip-path="url(#canvas)">
  {"".join(streets)}
  {"".join(labels)}
  </g>
  <path class="rt glow" d="{MAP["route"]}"/>
  <path class="rt walk" d="{MAP["route"]}"/>
  {"".join(pt_svg)}
  <g class="me" id="me" hidden><circle class="me-halo" r="14"/><circle class="me-acc" r="0"/><circle class="me-dot" r="4.5"/></g>
  <g class="scale"><line x1="20" y1="578" x2="{20+scale_px:.1f}" y2="578"/><text class="ml dim" x="20" y="572">500 m</text></g>
  <g class="north"><text class="ml dim" x="576" y="24" text-anchor="middle">N</text><line x1="576" y1="30" x2="576" y2="46"/></g>
</svg>'''

km = MAP["total_m"]/1000
mins = round(MAP["total_m"]/1000/4.4*60/5)*5
def kmf(m): return ("%.1f km" % (m/1000)).replace(".", ",")

def stop_html(s, i):
    cum = kmf(s["cum_m"])
    where = ""
    if s.get("maps"):
        where = '<p class="where"><span>%s</span><a href="%s" target="_blank" rel="noopener">Open in Maps</a></p>' % (esc(s.get("addr", "")), esc(s["maps"]))
    more = ""
    if s.get("more"):
        more = '<details class="more"><summary>More</summary><div class="more-body">%s</div></details>' % "".join("<p>%s</p>" % m for m in s["more"])
    accent = '<p class="accent">%s</p>' % s["accent"] if s.get("accent") else ""
    return f'''    <article class="stop" data-km="{s["cum_m"]/1000:.3f}">
      <span class="dot"></span>
      <div class="time">{cum}</div>
      <h3 class="title">{s["title"]}</h3>
      <p class="note">{s["note"]}</p>
      {accent}{where}{more}
    </article>'''

STOPS_HTML = "\n".join(stop_html(s, i) for i, s in enumerate(MAP["stop_copy"]))

page = open(sys.argv[3]).read()
page = (page.replace("{{SVG}}", svg)
            .replace("{{KM}}", ("%.1f" % km).replace(".", ","))
            .replace("{{MIN}}", str(mins))
            .replace("{{STOPS}}", STOPS_HTML)
            .replace("{{MINLON}}", repr(P["MINLON"])).replace("{{MAXLAT}}", repr(P["MAXLAT"]))
            .replace("{{K}}", repr(P["K"])).replace("{{SX}}", repr(P["SX"]))
            .replace("{{HX}}", "%.1f" % hx).replace("{{HY}}", "%.1f" % hy)
            .replace("{{HLAT}}", repr(home["latlon"][0])).replace("{{HLON}}", repr(home["latlon"][1])))
open(OUT, "w").write(page)
print("wrote", OUT, len(page), "bytes;", "%.2f km" % km, mins, "min")
