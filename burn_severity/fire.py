"""A fire's config (fires/<id>.json), its perimeter from NIFC WFIGS, and the shared 20 m UTM grid every map is put on."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio import features

ROOT = Path(__file__).resolve().parent.parent
WFIGS = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
         "WFIGS_Interagency_Perimeters/FeatureServer/0/query")
RES = 20.0          # m: Sentinel-2's B8A/B12 grid; every source is put on this grid (nearest for classes)
PAD_M = 1500        # grid margin around the perimeter (the ring offset needs it)
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}  # without it, signed blob URLs can open ungeoreferenced

# Four classes, shared by every source (MTBS's moderate-low and moderate-high merged); 0 = not seen / no data
CLASSES = {1: "unburned to low", 2: "low", 3: "moderate", 4: "high"}


@dataclass
class Fire:
    cfg: dict

    @property
    def id(self) -> str:
        return self.cfg["id"]

    @property
    def data(self) -> Path:
        p = ROOT / "data" / self.id
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache(self) -> Path:
        p = ROOT / "cache" / self.id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def perimeter(self) -> gpd.GeoSeries:
        """The incident team's latest perimeter (cached in data/ so a report pins the shape it used)."""
        p = self.data / "perimeter.geojson"
        if not p.exists():
            q = {"where": f"attr_UniqueFireIdentifier = '{self.cfg['wfigs_id']}'", "outFields": "poly_IncidentName,"
                 "poly_GISAcres,poly_DateCurrent,poly_MapMethod,attr_UniqueFireIdentifier", "outSR": 4326, "f": "geojson",
                 "geometry": ",".join(map(str, self.cfg["wfigs_bbox"])), "geometryType": "esriGeometryEnvelope",
                 "inSR": 4326, "spatialRel": "esriSpatialRelIntersects"}
            r = requests.post(WFIGS, data=q, timeout=120)
            r.raise_for_status()
            fc = r.json()
            if len(fc.get("features", [])) != 1:
                raise SystemExit(f"expected one WFIGS perimeter for {self.cfg['wfigs_id']}, got {len(fc.get('features', []))}")
            p.write_text(json.dumps(fc))
        return gpd.read_file(p).to_crs(self.cfg["crs"]).geometry

    def grid(self) -> tuple[rasterio.Affine, tuple[int, int]]:
        l, b, r, t = self.perimeter().buffer(PAD_M).total_bounds
        l, t = np.floor(l / RES) * RES, np.ceil(t / RES) * RES
        shape = (int(np.ceil((t - b) / RES)), int(np.ceil((r - l) / RES)))
        return rasterio.transform.from_origin(l, t, RES, RES), shape

    def inside(self) -> np.ndarray:
        t, shape = self.grid()
        return features.rasterize([(g, 1) for g in self.perimeter()], out_shape=shape, transform=t).astype(bool)

    def write(self, name: str, arr: np.ndarray, folder: Path | None = None) -> Path:
        """A class map (uint8, 0 = not seen) on the fire's grid, as a small compressed GeoTIFF."""
        t, shape = self.grid()
        p = (folder or self.data) / f"{name}.tif"
        with rasterio.open(p, "w", driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="uint8", nodata=0,
                           crs=self.cfg["crs"], transform=t, compress="deflate") as dst:
            dst.write(arr.astype("uint8"), 1)
        return p

    def read(self, name: str, folder: Path | None = None) -> np.ndarray:
        with rasterio.open((folder or self.data) / f"{name}.tif") as src:
            return src.read(1)


def load(fire_id: str) -> Fire:
    return Fire(json.loads((ROOT / "fires" / f"{fire_id}.json").read_text()))


def classify(dnbr: np.ndarray, low: float, moderate: float, high: float) -> np.ndarray:
    """Continuous dNBR → the four shared classes with the given thresholds; NaN → 0 (not seen)."""
    out = np.select([dnbr < low, dnbr < moderate, dnbr < high, dnbr >= high], [1, 2, 3, 4], 0).astype("uint8")
    out[~np.isfinite(dnbr)] = 0
    return out
