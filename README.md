# Routes

Walks from the front door, each as a one-page, phone-first site in the DARIDEH style, with a street map drawn from OpenStreetMap data rather than map tiles.

- Live: https://depross.github.io/routes/
- `helleketelbos/` — Helleketelbos loop from Kleine Dasdreef, 5,6 km, about 75 min.

## How a route page is built

1. **Street data.** Two GitHub Actions fetch OpenStreetMap geometry for a bounding box and commit it under `data/`:
   - `Fetch OSM data` queries the public Overpass API (fast when the servers are responsive, often not).
   - `Extract OSM data (Geofabrik)` downloads the Belgium extract and cuts the box out with osmium. Slower to start, always works. This is the one that produced `data/helleketel.geojson.gz`.
   Run either from the Actions tab with a bbox and a name.
2. **Route.** `tools/build_map.py` builds a walking graph from the OSM ways (paths and tracks preferred over lanes, lanes over through roads), snaps the waypoints listed at the top of the file to the network, runs shortest paths between them and closes the loop. It also projects every street into a 600×600 canvas and writes `map.json`.
3. **Page.** `tools/build_page.py map.json <out>/index.html tools/template.html` fills the template with the SVG, the stop list (distances from the door) and the projection constants used by the live-location dot.
4. **Check.** `tools/render_check.py <out>/index.html check.png` rasterises the map for a look before pushing.

Everything on the published page is static: no map tiles, no API keys, no runtime fetches. Location is the only thing that runs on the phone, and only when switched on.
