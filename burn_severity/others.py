"""Official sources, put on the fire's grid with nearest-neighbour resampling (classes are categories).

- Official products from the USGS/USFS Burn Severity Portal (public domain), from the zips it emails: the BAER and
  RAVG bundles. Their dNBR is classed twice, with the analyst's thresholds and with Key & Benson's, which separates a
  difference in images from a difference in judgement. RAVG's 4-class composite burn index is used as delivered.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from .fire import Fire, classify
from .s2 import KEY_BENSON

def _on_grid(fire: Fire, path: Path, continuous: bool) -> np.ndarray:
    """Nearest-neighbour onto the fire's grid. Continuous layers: -32768 (used, though not declared) → NaN."""
    t, shape = fire.grid()
    with rasterio.open(path) as s:
        a = s.read(1)
        if continuous:
            a = np.where(a == -32768, np.nan, a).astype("float32")
        out = np.full(shape, np.nan if continuous else 0, "float32" if continuous else "uint8")
        reproject(a, out, src_transform=s.transform, src_crs=s.crs, dst_transform=t, dst_crs=fire.cfg["crs"],
                  resampling=Resampling.nearest, src_nodata=np.nan if continuous else 0,
                  dst_nodata=np.nan if continuous else 0)
    return out


# The portal's bundle layers we use, by file-name ending (bundles: <prog>/<year>/<event id>/<event>_<pre>_<post>_*.tif)
OFFICIAL = {
    ("baer", "_dnbr_barc4.tif"): ("baer-barc4", False),     # the analyst's 4 classes, as delivered
    ("baer", "_dnbr.tif"): ("baer-keybenson", True),        # the same dNBR, classed with Key & Benson
    ("ravg", "_rdnbr_cbi4.tif"): ("ravg-cbi4", False),      # RdNBR → composite burn index, field-calibrated, 4 classes
}


def official(fire: Fire, zips: list[Path]) -> list[str]:
    """Unpack the portal's zips into cache/ and write the official class maps (public domain) to data/."""
    out = fire.cache / "official"
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(out / z.stem)
    written = []
    for p in sorted(out.rglob("*.tif")):
        prog = p.relative_to(out).parts[1]
        for (pr, end), (name, continuous) in OFFICIAL.items():
            if pr == prog and p.name.endswith(end) and not p.name.endswith("r" + end[1:]):  # _dnbr ≠ _rdnbr
                a = _on_grid(fire, p, continuous)
                fire.write(name, classify(a, *KEY_BENSON) if continuous else np.where(np.isin(a, [1, 2, 3, 4]), a, 0))
                written.append(name)
    if not written:
        raise SystemExit(f"no known layers among: {[p.name for p in out.rglob('*.tif')]}")
    return sorted(set(written))
