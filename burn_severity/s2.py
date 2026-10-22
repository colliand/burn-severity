"""Our estimate: Sentinel-2 L2A dNBR from per-pixel median composites, ring-offset, Key & Benson classes.

The same method as whatcom.land's Fires › Recent fires (pipeline/build_fires_recent.py there); this copy writes the
continuous dNBR too, so it can be compared pixel by pixel with the official products.

  1. Pre and post windows from the fire's config. Clear views only (SCL 4 vegetation, 5 bare soil).
  2. NBR = (B8A − B12) / (B8A + B12) after removing the +1000 offset of processing baseline 04.00+.
  3. Per-pixel median NBR of each window; pixels with fewer than MIN_VIEWS clear views, or ever water (JRC), are NaN.
  4. dNBR = 1000 × (pre − post), minus the median dNBR of a ring 300–1500 m outside the perimeter.
  5. Key & Benson (2006) thresholds: 100 / 270 / 660.
"""
from __future__ import annotations

import warnings
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio import features
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

from .fire import GDAL_ENV, Fire, classify

PC = "https://planetarycomputer.microsoft.com/api"
JRC = "https://ai4edataeuwest.blob.core.windows.net/jrcglobalwater/occurrence/occurrence_130W_50Nv1_3_2020cog.tif"
MIN_VIEWS = 2
RING_M = (300, 1500)
KEY_BENSON = (100, 270, 660)


def _nbr_median(fire: Fire, items: list, token: str) -> tuple[np.ndarray, np.ndarray]:
    t, shape = fire.grid()
    crs = fire.cfg["crs"]

    def read(href, resampling):
        out = np.zeros(shape, "float32")
        with rasterio.Env(**GDAL_ENV), rasterio.open(f"{href}?{token}") as s:
            reproject(rasterio.band(s, 1), out, dst_transform=t, dst_crs=crs, resampling=resampling, dst_nodata=0)
        return out

    def one(f):
        a = f["assets"]
        off = 1000 if float(f["properties"].get("s2:processing_baseline", "0")) >= 4 else 0
        scl = read(a["SCL"]["href"], Resampling.nearest)
        nir = read(a["B8A"]["href"], Resampling.bilinear) - off
        swir = read(a["B12"]["href"], Resampling.bilinear) - off
        ok = np.isin(scl, [4, 5]) & (nir > 0) & (swir > 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(ok, (nir - swir) / (nir + swir), np.nan).astype("float32")

    with ThreadPoolExecutor(8) as ex:
        stack = np.stack(list(ex.map(one, items)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(stack, 0), np.sum(np.isfinite(stack), 0)


def _water(fire: Fire) -> np.ndarray:
    """Ever-water pixels (JRC occurrence > 0). Read the window, then reproject the array: reprojecting straight from
    this 40,000² file's band marked every pixel as water."""
    t, shape = fire.grid()
    l, b = t.c, t.f - shape[0] * t.e * -1
    r, top = t.c + shape[1] * t.a, t.f
    occ = np.zeros(shape, "uint8")
    signed = requests.get(f"{PC}/sas/v1/sign", params={"href": JRC}, timeout=60).json()["href"]
    with rasterio.Env(**GDAL_ENV), rasterio.open(signed) as s:
        w = from_bounds(*transform_bounds(fire.cfg["crs"], s.crs, l, b, r, top, densify_pts=21), s.transform)
        w = w.round_offsets().round_lengths()
        reproject(s.read(1, window=w, boundless=True, fill_value=0), occ, src_transform=s.window_transform(w),
                  src_crs=s.crs, dst_transform=t, dst_crs=fire.cfg["crs"], resampling=Resampling.nearest)
    return occ > 0


def estimate(fire: Fire, kind: str) -> dict:
    """Write data/<fire>/ours-<kind>-dnbr.tif (continuous, ×1000, int16) and ours-<kind>.tif (classes)."""
    win = fire.cfg["windows"][kind]
    t, shape = fire.grid()
    per = fire.perimeter()
    aoi = gpd.GeoSeries([per.union_all().envelope], crs=fire.cfg["crs"]).to_crs(4326).iloc[0].__geo_interface__
    token = requests.get(f"{PC}/sas/v1/token/sentinel-2-l2a", timeout=60).json()["token"]

    def scenes(d0, d1):
        body = {"collections": ["sentinel-2-l2a"], "intersects": aoi, "datetime": f"{d0}/{d1}",
                "query": {"eo:cloud_cover": {"lt": 70}}, "limit": 250}
        r = requests.post(f"{PC}/stac/v1/search", json=body, timeout=180)
        r.raise_for_status()
        return r.json()["features"]

    pre_items, post_items = scenes(*win["pre"]), scenes(*win["post"])
    pre, npre = _nbr_median(fire, pre_items, token)
    post, npost = _nbr_median(fire, post_items, token)
    d = 1000 * (pre - post)
    d[(npre < MIN_VIEWS) | (npost < MIN_VIEWS) | _water(fire)] = np.nan
    g = per.union_all()
    ring = features.rasterize([(g.buffer(RING_M[1]).difference(g.buffer(RING_M[0])), 1)], out_shape=shape,
                              transform=t).astype(bool)
    offset = float(np.nanmedian(d[ring]))
    d -= offset
    with rasterio.open(fire.data / f"ours-{kind}-dnbr.tif", "w", driver="GTiff", height=shape[0], width=shape[1],
                       count=1, dtype="int16", nodata=-32768, crs=fire.cfg["crs"], transform=t, compress="deflate") as dst:
        dst.write(np.where(np.isfinite(d), np.round(d), -32768).astype("int16"), 1)
    fire.write(f"ours-{kind}", classify(d, *KEY_BENSON))
    dates = sorted({f["properties"]["datetime"][:10] for f in post_items})
    return {"kind": kind, "offset": round(offset), "pre_views": len(pre_items), "post_views": len(post_items),
            "post_dates": [dates[0], dates[-1]] if dates else None}
