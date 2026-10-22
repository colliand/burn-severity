"""Compare every class map of a fire inside its perimeter: shares per class, and agreement with a reference map."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .fire import CLASSES, Fire

ORDER = ["ravg-cbi4", "baer-barc4", "baer-keybenson", "ours-initial", "ours-extended"]


def maps(fire: Fire) -> dict[str, np.ndarray]:
    found = {}
    for name in ORDER:
        for folder in (fire.data,):
            if (folder / f"{name}.tif").exists():
                found[name] = fire.read(name, folder)
                break
    return found


def compare(fire: Fire, reference: str | None = None) -> pd.DataFrame:
    inside = fire.inside()
    ms = maps(fire)
    rows = []
    for name, a in ms.items():
        v = a[inside]
        seen = v[v > 0]
        row = {"map": name, "pct_not_seen": round(100 * (v == 0).mean(), 1)}
        row |= {CLASSES[k]: round(100 * (seen == k).mean(), 1) if len(seen) else None for k in CLASSES}
        rows.append(row)
    df = pd.DataFrame(rows)
    ref = reference or next((r for r in ("ravg-cbi4", "baer-barc4") if r in ms), None)
    agree = {}
    if ref:
        r = ms[ref]
        for name, a in ms.items():
            if name == ref:
                continue
            m = inside & (r > 0) & (a > 0)
            if not m.any():
                continue
            cm = np.zeros((4, 4), int)
            np.add.at(cm, (r[m].astype(int) - 1, a[m].astype(int) - 1), 1)
            agree[name] = {"exact_pct": round(100 * np.trace(cm) / cm.sum(), 1),
                           "within_one_pct": round(100 * (np.abs(r[m].astype(int) - a[m].astype(int)) <= 1).mean(), 1),
                           "pixels": int(cm.sum()), "matrix_rows_reference": cm.tolist()}
        df["agrees_with_" + ref] = df["map"].map(lambda n: agree.get(n, {}).get("exact_pct"))
    df.to_csv(fire.data / "compare.csv", index=False)
    (fire.data / "agreement.json").write_text(json.dumps({"reference": ref, "classes": CLASSES, "maps": agree}, indent=1))
    return df
