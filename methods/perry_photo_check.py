"""Perry 2025: a blind look at Sentinel-2 natural-colour images where the official maps and ours disagree.

    uv run python methods/perry_photo_check.py sheets   # → methods/perry-photo-check/sheet_*.jpg, key.json (key hidden from the rater)
    uv run python methods/perry_photo_check.py score     # after rating: ratings.json + key.json → summary

Sample (seeded): spots 60 m across (3 × 3 pixels of 20 m) whose classes are uniform in each map, in four strata:
  A  BAER low, RAVG moderate                  (the two official maps disagree)
  B  BAER moderate, RAVG high
  C  ours-initial moderate, RAVG low           (our biggest disagreement with RAVG)
  D  RAVG, BAER and ours all high / E all three low (controls)
Each spot: Sentinel-2 natural colour (B04/B03/B02, 10 m) on 24 Aug 2025 (before), 18 Sep 2025 (three weeks after)
and the clearest summer 2026 scene (a year after), 1 km around the spot, numbered in random order.
"""
import json, random, sys
from pathlib import Path
import numpy as np, rasterio, requests
from rasterio.warp import Resampling, reproject
from scipy.ndimage import uniform_filter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from burn_severity.fire import GDAL_ENV, load  # noqa: E402
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent / "perry-photo-check"
PC = "https://planetarycomputer.microsoft.com/api"
DATES = {"before (24 Aug 2025)": "2025-08-24", "after (18 Sep 2025)": "2025-09-18", "a year after": "2026-07-15/2026-09-30"}
PER_STRATUM, HALF_M = 6, 500

def uniform(a, k):
    return uniform_filter(np.isin(a, k).astype(float), 3) > 0.99

def sample(fire):
    m = {n: fire.read(n) for n in ("ravg-cbi4", "ours-initial", "baer-barc4")}
    inside = fire.inside()
    r, o, b = m["ravg-cbi4"], m["ours-initial"], m["baer-barc4"]
    strata = {"A": uniform(b, 2) & uniform(r, 3), "B": uniform(b, 3) & uniform(r, 4), "C": uniform(o, 3) & uniform(r, 2),
              "D": uniform(r, 4) & uniform(o, 4) & uniform(b, 4), "E": uniform(r, 2) & uniform(o, 2) & uniform(b, 2)}
    rng = random.Random(202610222)
    t, _ = fire.grid()
    spots = []
    for s, mask in strata.items():
        ys, xs = np.nonzero(mask & inside)
        idx = list(range(len(ys))); rng.shuffle(idx)
        chosen = []
        for i in idx:  # spread out: at least 300 m apart
            y, x = ys[i], xs[i]
            if all((y - cy) ** 2 + (x - cx) ** 2 >= 15 ** 2 for cy, cx in chosen):  # 300 m
                chosen.append((y, x))
            if len(chosen) == PER_STRATUM:
                break
        for y, x in chosen:
            X, Y = t * (x + 0.5, y + 0.5)
            spots.append({"stratum": s, "x": X, "y": Y, **{k: int(v[y, x]) for k, v in m.items()}})
        print(s, len(ys), "candidate pixels,", len(chosen), "chosen")
    rng.shuffle(spots)
    for i, sp in enumerate(spots, 1):
        sp["n"] = i
    return spots

def scene(fire, when, token):
    import geopandas as gpd
    aoi = gpd.GeoSeries([fire.perimeter().union_all().envelope], crs=fire.cfg["crs"]).to_crs(4326).iloc[0].__geo_interface__
    dt = when if "/" in when else f"{when}T00:00:00Z/{when}T23:59:59Z"
    fs = requests.post(f"{PC}/stac/v1/search", json={"collections": ["sentinel-2-l2a"], "intersects": aoi, "datetime": dt,
                       "query": {"eo:cloud_cover": {"lt": 20}}, "limit": 100}, timeout=120).json()["features"]
    f = sorted(fs, key=lambda f: f["properties"]["eo:cloud_cover"])[0]
    return f["assets"]["visual"]["href"] + "?" + token, f["properties"]["datetime"][:10]

def chip(href, x, y, crs):
    res = 10
    t = rasterio.transform.from_origin(x - HALF_M, y + HALF_M, res, res); n = 2 * HALF_M // res
    out = np.zeros((3, n, n), "uint8")
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as s:
        for i in range(3):
            reproject(rasterio.band(s, i + 1), out[i], dst_transform=t, dst_crs=crs, resampling=Resampling.bilinear)
    return np.moveaxis(out, 0, -1)

def sheets():
    fire = load("perry-2025"); OUT.mkdir(exist_ok=True)
    spots = sample(fire)
    token = requests.get(f"{PC}/sas/v1/token/sentinel-2-l2a", timeout=60).json()["token"]
    hrefs = {k: scene(fire, v, token) for k, v in DATES.items()}
    print({k: d for k, (_, d) in hrefs.items()})
    for s0 in range(0, len(spots), 5):
        rows = spots[s0:s0 + 5]
        fig, ax = plt.subplots(len(rows), 3, figsize=(10.5, 3.6 * len(rows)), squeeze=False)
        for i, sp in enumerate(rows):
            for j, (label, (href, day)) in enumerate(hrefs.items()):
                img = chip(href, sp["x"], sp["y"], fire.cfg["crs"])
                a = ax[i][j]; a.imshow(np.clip(img.astype(float) / np.percentile(img, 99.5), 0, 1))
                a.add_patch(plt.Rectangle((46, 46), 8, 8, fill=False, ec="yellow", lw=1.5))  # the 60 m spot
                a.set_title(f"#{sp['n']}  {label.split(' (')[0]} {day}", fontsize=9); a.set_xticks([]); a.set_yticks([])
        fig.tight_layout(); fig.savefig(OUT / f"sheet_{s0 // 5 + 1:02d}.jpg", dpi=70); plt.close(fig)
    (OUT / "key.json").write_text(json.dumps({"scenes": {k: d for k, (_, d) in hrefs.items()}, "spots": spots}, indent=1))
    print(len(spots), "spots")

def score():
    key = json.loads((OUT / "key.json").read_text())["spots"]
    ratings = json.loads((OUT / "ratings.json").read_text())
    by = {}
    for sp in key:
        r = ratings[str(sp["n"])]
        by.setdefault(sp["stratum"], []).append(r)
    for s in sorted(by):
        print(s, {k: by[s].count(k) for k in sorted(set(by[s]))})

{"sheets": sheets, "score": score}[sys.argv[1]]()
