# burn-severity

Burn-severity maps of one fire, put on one grid, compared, and used to tune our own method. One config file per fire
(`fires/<id>.json`). Built for whatcom.land, whose Fires › Recent fires view shows our Sentinel-2 estimate before the
official maps arrive.

Burn severity is a measurement with a date and a set of judgement calls: which images, how soon after the fire, which
index, which thresholds. Official products (USGS BAER, USFS RAVG, MTBS) are reference points made by experts, not
ground truth. This repo lays them side by side with our own estimate and other public maps, so the differences can be
seen and explained, checked against the images, and used to improve our estimate.

    uv run python -m burn_severity perimeter perry-2025                  # NIFC WFIGS perimeter → data/perry-2025/
    uv run python -m burn_severity ours perry-2025 initial                # our Sentinel-2 dNBR, soon after the fire
    uv run python -m burn_severity ours perry-2025 extended               # ... and the summer after
    uv run python -m burn_severity official perry-2025 ~/Downloads/*.zip  # BAER / RAVG bundles from the portal
    uv run python -m burn_severity compare perry-2025                     # → data/perry-2025/compare.csv, agreement.json
    uv run python -m burn_severity calibrate perry-2025                   # thresholds that best match RAVG → calibration.json
    uv run python methods/perry_photo_check.py sheets                     # blind image check of the disagreements

Every map is put on a 20 m UTM grid (Sentinel-2's B8A/B12 grid) with nearest-neighbour resampling, and reduced to four
classes: unburned to low, low, moderate (MTBS's moderate-low and moderate-high together), high. 0 = not seen.

**Our estimate** (`burn_severity/s2.py`): per-pixel median NBR of clear Sentinel-2 L2A views (SCL 4–5) before and after,
baseline-04.00 offset removed, dNBR × 1000 minus the median of a ring 300–1500 m outside the perimeter, Key & Benson
(2006) thresholds 100 / 270 / 660, ever-water pixels (JRC) left out.

**Official maps**: the BAER team's analyst classes (BARC) as delivered; the same USGS dNBR classed with Key & Benson's
thresholds; and RAVG's composite burn index (RdNBR, calibrated on field plots). Where BAER and the USGS dNBR with
textbook thresholds differ, the disagreement is about judgement, not images.

**Harmonization** (`burn_severity/calibrate.py`): the three thresholds on our dNBR that best reproduce RAVG, fitted on
the whole fire and on its west half, tested on the east half.

Reports: `methods/<fire>.md`, and the matching page on notes.colliand.com.

Data: NIFC WFIGS perimeters (public domain); Sentinel-2 L2A (contains modified Copernicus Sentinel data) via
Microsoft Planetary Computer; JRC Global Surface Water (Pekel et al. 2016); USGS/USFS Burn Severity Portal products
(public domain).
