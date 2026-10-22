"""Harmonization: which class thresholds on our dNBR best reproduce a field-calibrated reference map (RAVG CBI)?

Grid search over three thresholds (low / moderate / high), scored by the share of pixels in the same class as the
reference inside the perimeter. To check that a fit is not just memorising one fire, it is also fitted on the west half
of the fire and tested on the east half (a crude spatial hold-out). One fire is not enough to change a method: the
next step is the same fit across many fires with RAVG or MTBS maps.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import rasterio

from .fire import Fire, classify
from .s2 import KEY_BENSON

GRID = [t for t in itertools.product(range(40, 201, 10), range(150, 451, 10), range(300, 801, 10)) if t[0] < t[1] < t[2]]


def _dnbr(fire: Fire, name: str) -> np.ndarray:
    with rasterio.open(fire.data / f"{name}.tif") as s:
        a = s.read(1).astype("float32")
    a[a == -32768] = np.nan
    return a


def _acc(d, ref, mask, th) -> float:
    return float((classify(d, *th)[mask] == ref[mask]).mean())


def _best(d, ref, mask) -> tuple[float, tuple]:
    return max((_acc(d, ref, mask, th), th) for th in GRID)


def calibrate(fire: Fire, reference: str = "ravg-cbi4") -> dict:
    ref = fire.read(reference)
    base = fire.inside() & (ref > 0)
    out = {"reference": reference, "textbook": list(KEY_BENSON), "runs": {}}
    for kind in ("initial", "extended"):
        d = _dnbr(fire, f"ours-{kind}-dnbr")
        ok = base & np.isfinite(d)
        cols = np.nonzero(ok.any(0))[0]
        mid = (cols.min() + cols.max()) // 2
        west, east = ok.copy(), ok.copy()
        west[:, mid:] = False
        east[:, :mid] = False
        acc, th = _best(d, ref, ok)
        _, th_w = _best(d, ref, west)
        out["runs"][kind] = {"textbook_agreement": round(_acc(d, ref, ok, KEY_BENSON), 3),
                             "fitted_thresholds": list(th), "fitted_agreement": round(acc, 3),
                             "holdout": {"fitted_on_west": list(th_w), "east_agreement": round(_acc(d, ref, east, th_w), 3),
                                         "east_agreement_textbook": round(_acc(d, ref, east, KEY_BENSON), 3)}}
    (fire.data / "calibration.json").write_text(json.dumps(out, indent=1))
    return out
