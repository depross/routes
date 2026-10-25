# Routes

Walks from the front door, each as a one-page, phone-first site in the DARIDEH style, with a street map drawn from OpenStreetMap data rather than map tiles.

- Live: https://depross.github.io/routes/
- Routes are grouped by category and size (S up to 4 km, M 4 to 8, L 8 to 13, XL above). Nature: `nature/s` (field path, 3,0 km, draft), `nature/m` (Helleketelbos, 6,3 km), `nature/l` (old railway and wood, 10,6 km), `nature/xl` (three woods, 17,3 km). History: `history/l` (9,6 km), `history/xl` (16,1 km). City: `city/l` (9,3 km). Beer & hops: `beer/xl` (19,9 km). Border: `border/xl` (17,7 km).
- Each route is one JSON config in `routes/`; the page is generated from it.

## How a route page is built

1. **Street data.** Two GitHub Actions fetch OpenStreetMap geometry for a bounding box and commit it under `data/`:
   - `Fetch OSM data` queries the public Overpass API (fast when the servers are responsive, often not).
   - `Extract OSM data (Geofabrik)` downloads the Belgium extract and cuts the box out with osmium. Slower to start, always works. `data/poperinge-wide.geojson.gz` (12 × 14 km around the house) is what the current routes use.
   Run either from the Actions tab with a bbox and a name.
2. **Config.** `routes/<slug>.json` holds the home coordinate, the waypoints in walking order (with the stop copy: title, note, accent, Maps link), optional unmapped `links`, extra markers, street names to label, and the page texts.
3. **Build.** `python3 -I tools/build.py routes/<slug>.json` builds a walking graph from the OSM ways (paths and tracks preferred over lanes, lanes over through roads; private lanes only within 350 m of home), snaps the waypoints, runs shortest paths between them, closes the loop at the front door, projects everything into a 600 × 600 canvas and writes `<out>/index.html` plus a `check.png` of the map (git-ignored).
4. **Explore.** `python3 -I tools/explore.py data/<file> candidates.json [debug.png]` measures candidate loops (length, unpaved share, street sequence) before committing to one.

Everything on the published page is static: no map tiles, no API keys, no runtime fetches. Location is the only thing that runs on the phone, and only when switched on.
