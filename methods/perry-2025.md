# Perry fire, 2025: one fire, several severity maps, and a better estimate

Status: **draft**. Official BAER and RAVG bundles received 2026-10-22 (Burn Severity Portal, UTM).

## The fire

Started 28 August 2025 in North Cascades National Park, Whatcom County, Washington. 1,772 acres by the NIFC WFIGS
perimeter (1,782 in the official burned-area boundary). A Park Service fire, so no Forest Service RAVG mosaic coverage
(it has a RAVG "Initial" record but is absent from the 2025 national mosaic). It is above MTBS's 1,000-acre threshold
for the West, so MTBS will map it in a year or two.

## The maps

| map | images | when after the fire | thresholds | made by |
|---|---|---|---|---|
| ours-initial | Sentinel-2 medians, 10 Sep – 13 Oct 2025 | weeks | Key & Benson | this repo |
| ours-extended | Sentinel-2 medians, summer 2026 | one year | Key & Benson | this repo |
| baer-barc4 | Sentinel-2, one scene each: 24 Aug (S2B) / 18 Sep 2025 (S2C) | three weeks | analyst (BARC, set on a 0–255 rescaling: 75 / 133 / 191, "nonstandard") | USGS EROS for the BAER team |
| baer-keybenson | the same USGS dNBR | three weeks | Key & Benson | this repo, from USGS dNBR |
| ravg-cbi4 | the same two scenes | three weeks | RdNBR → composite burn index, field-calibrated | USFS RAVG |
| MTBS | Landsat, extended | a year or more | analyst | not yet published |

## Results

Inside the WFIGS perimeter, 20 m grid, % of the area seen (`data/perry-2025/compare.csv`), and pixel agreement with
RAVG's composite burn index (`agreement.json`):

| map | unburned–low | low | moderate | high | same class as RAVG | within one class |
|---|---|---|---|---|---|---|
| ravg-cbi4 (reference) | 14 | 49 | 22 | 16 | — | — |
| baer-barc4 | 24 | 53 | 16 | 7 | 69% | 99% |
| baer-keybenson | 24 | 39 | 29 | 8 | 77% | 99.7% |
| ours-initial | 21 | 32 | 33 | 14 | 72% | 99.7% |
| ours-extended (a year later) | 11 | 25 | 52 | 12 | 47% | 97% |

Findings:

1. **The two official maps disagree with each other, from the same two images.** BAER's analyst classes give 7% high;
   RAVG's field-calibrated burn index gives 16%. Classing USGS's dNBR with the textbook thresholds gives 8%. The
   difference is method and judgement, not data: severity is a measurement with judgement calls.
2. **Our initial estimate agrees with RAVG as well as USGS's own BAER map does** (72% vs 69% same class; 99.7% within
   one class), from independent processing (medians of 13 views vs one scene pair). We read more moderate than RAVG,
   where RAVG says low.
3. **Our extended estimate differs most from the initial maps**, as expected. It measures a year later, after more
   trees died (moderate 52%). The official one-year-later map, MTBS, is the right referee for it, when it comes.

## Harmonization: tuning our thresholds to the field-calibrated map

`calibrate` searches thresholds on our dNBR for the best match with RAVG's composite burn index (`calibration.json`):

| our map | textbook (100 / 270 / 660) | fitted, whole fire | fitted on the west half → east half (textbook on east) |
|---|---|---|---|
| initial | 72% | 80% at 70 / 360 / 650 | 80 / 290 / 620 → 75% (70%) |
| extended | 47% | 61% at 80 / 450 / 660 | 50 / 450 / 540 → 62% (45%) |

The gain survives the hold-out, so it is not only memorising the fire. For the initial map the main change is a higher
low/moderate line (about 300–360 instead of 270): our medians read slightly hotter than RAVG in the low range. For the
extended map the moderate line moves up a lot (450), as expected a year later. One fire is not enough to change the
method on whatcom.land; the next step is the same fit across many fires with RAVG or MTBS maps, then a single set of
thresholds with its uncertainty.

## A blind look at the images

No aerial photos of Perry after the fire are public (Washington's latest NAIP in the archives is 2023). The sharpest
independent look is Sentinel-2's 10 m natural-colour image. `methods/perry_photo_check.py` picks 30 spots 60 m across
(seeded), six in each of five strata, and shows each before (24 Aug 2025), three weeks after (18 Sep 2025) and a year
after (18 Sep 2026; mostly cloudy, little used). Spots were rated green / mixed / dead / unreadable without the key
(`perry-photo-check/ratings.json`), then unblinded.

| stratum | green | mixed | dead | unreadable |
|---|---|---|---|---|
| RAVG, BAER and ours all high (control) | 0 | 0 | 6 | 0 |
| all three low (control) | 1 | 3 | 1 | 1 |
| BAER low, RAVG moderate | 0 | 6 | 0 | 0 |
| BAER moderate, RAVG high | 0 | 1 | 5 | 0 |
| ours moderate, RAVG low | 0 | 4 | 0 | 2 |

- The eye agrees with high where all maps say high.
- The eye cannot tell low from moderate: spots every map calls low often look browned (scorched needles, late-summer
  drying). So the low/moderate disagreements (BAER low vs RAVG moderate; ours moderate vs RAVG low) stay open.
- Where BAER says moderate and RAVG says high, five of six spots look like the high control. On that boundary the
  field-calibrated map looks right, and the analyst's lines undercall high severity. This supports tuning toward RAVG.

Limits: six spots a stratum; one rater (an AI model reading the images, so a second human rater would help); and the
"after" image is the very scene both official maps used, so this checks the classification, not the data. A field
visit, or NAIP when Washington is next flown, would be independent.


## Questions this should answer

1. Do our estimate and the official dNBR differ because of the images, or because of the thresholds?
2. How much did severity change between the initial and the extended assessment?
3. Which thresholds, fitted across many fires, would make our estimate closest to the field-calibrated maps?
4. Where they all disagree, what does an independent look show (aerial photos, a site visit)?
