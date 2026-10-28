# Real passes, explained: the physics, the logic, and where every number comes from

Covers `script_code/real_pass.py`, `plots/plot_real_pass.py` and the Aqua results in `real_passes/AQUA_27424/`.
Each step names the data file it uses and the source of the physics.  References [R1]–[R12] are listed at the
end.  ✓ = checked, ⚠ = still to read or confirm yourself, ✎ = a choice made for this project.

---

## 1. The input: one line of orbit data (a TLE)

Everything starts from a **two-line element set (TLE)** downloaded from CelesTrak [R1] and saved, unchanged, in
`real_passes/AQUA_27424/sources/tle_20261028T202434Z.txt` (download time in `sources/fetch_log.json`):

```text
AQUA
1 27424U 02022A   26301.57246609  .00000373  00000+0  83860-4 0  9997
2 27424  98.4467 273.6488 0000816  94.4519  15.5601 14.62254291302766
```

The TLE format and the model it is made for are defined in *Spacetrack Report No. 3* [R2] (updated by
[R3]).  The fields used here:

| Field (columns) | Value | Meaning |
|---|---|---|
| Line 1, 3–7 | 27424 | catalogue number (Aqua) |
| Line 1, 19–32 | 26301.57246609 | epoch: year 2026, day 301.572 = 28 Oct 2026 13:44 UTC, the moment the elements describe |
| Line 2, 9–16 | 98.4467° | inclination: tilt of the orbit to the equator (over 90° = slightly retrograde, as for every sun-synchronous orbit) |
| Line 2, 27–33 | 0.0000816 | eccentricity: 0 would be a perfect circle |
| Line 2, 53–63 | 14.62254291 rev/day | mean motion: orbits per day |

## 2. From those numbers to the orbit (worked by hand; constants from NASA's Earth fact sheet [R4])

**Period.**  T = 1 day ÷ mean motion = 86,400 s ÷ 14.6225 = **5,909 s = 98.48 min**.

**Size of the orbit (Kepler's third law).**  For an orbit of period T around a mass with GM = 398,600.4 km³ s⁻²:

  a = (GM / ω²)^⅓,  ω = 2π / T   →   **a = 7,064 km** from Earth's centre.

**Height.**  a − R: **686 km** above the equatorial radius (6,378.137 km), **693 km** above the mean radius
(6,371 km).  The eccentricity is tiny, so the orbit is almost circular: perigee 685.3 km, apogee 686.5 km.
This is why Aqua's real passes come out lower than its **705 km design height** (§10, check 4).

**Why the passes happen at the same times of day (sun-synchronous orbit).**  Earth's equatorial bulge
(measured by J₂ = 1.08263 × 10⁻³ [R4]) slowly turns the orbit's plane.  To first order [R5]:

  dΩ/dt = −(3/2) · n · J₂ · (R_eq / a)² · cos i / (1 − e²)²

With Aqua's numbers this is **+1.024° per day**.  A sun-synchronous orbit needs +360° / 365.2422 days =
**0.9856° per day** [R5], so the plane keeps pace with the Sun and the satellite crosses each latitude at the
same local time every day (for Aqua, about 1:30 pm going north and 1:30 am going south [R6]).  That is why
the passes in the figure come in a morning group and an afternoon group.  The current orbit turns about **4 %
faster** than exactly sun-synchronous, which is consistent with Aqua having been lowered from its controlled
orbit (§10, check 4); ✎ this first-order formula ignores smaller effects, so treat the 4 % as approximate.

## 3. Where the satellite is at any moment: SGP4

A TLE is not a snapshot of position: it is a set of *mean* elements fitted to tracking data for one specific
model, **SGP4** [R2, R3].  Using a different orbit model on a TLE gives worse positions, so the script uses SGP4.
It runs through Skyfield [R7], which calls the `sgp4` library implementing the corrected version of [R3], with
the WGS72 Earth model that TLEs are made with [R7].

**Accuracy.**  Quoting Vallado et al. as cited in Skyfield's documentation: TLE data "is accurate to about a
kilometer or so at epoch and it quickly degrades"; an element set is useful "for a couple of weeks to either
side of its epoch" [R7].  So every run saves the TLE's age (`run_info.json`: **0.28 days** for this run) and the
script downloads a fresh TLE whenever its copy is more than 2 hours old (✎).

## 4. What the observer sees: elevation, azimuth, distance

The observer is a point on the WGS84 ellipsoid at DCU, **53.384954° N, 6.256542° W** [R8], height 60 m (✎).
Skyfield subtracts the observer's position from the satellite's to get the line of sight [R7]:

* **Elevation (altitude):** angle above the horizon: 0° on the horizon, 90° straight overhead [R7].
* **Azimuth:** direction around the horizon, clockwise from north: 90° east, 180° south [R7].
* **Distance (range):** length of the line of sight.
* **Zenith angle** = 90° − elevation.

**Why distance grows so fast towards the horizon.**  In the triangle Earth's centre – observer – satellite the
cosine rule gives (derivation in `METHODS_AND_SOURCES.md` §4b):

  d = √[(R + h)² − (R cos e)²] − R sin e

For h = 693 km: **693 km overhead, 3,051 km on the horizon: 4.4 times further.**  Brightness falls as 1/d², so
from distance alone the same satellite is 4.4² ≈ 19 times (3.2 magnitudes) fainter on the horizon than
overhead.  ✓ The full calculation agrees with this formula to within 5 km (median 1 km) on every sample; the
small difference is because the formula treats the Earth as a sphere and the observer is on the ellipsoid.

## 5. Finding the passes: rise, highest point, set

Skyfield's `find_events` searches the time window for the moments the satellite crosses a chosen elevation
(here ✎ 0°, the horizon) and the moment of its highest elevation in between: event 0 = rise, 1 = highest
point ("culminate"), 2 = set [R7].  The script groups each rise–highest–set into one pass and samples it every
**5 s** (✎).

**How long can a pass last?**  The satellite is above the horizon while it is within an Earth-centred angle
λ = arccos(R / (R + h)) = **25.6°** of the observer.  A pass straight overhead crosses 2λ = 51.2° of the orbit,
which takes 51.2 / 360 × 98.5 min = **14.0 min** (ignoring Earth's rotation).  ✓ The longest pass in the data
lasts **13.9 min** (`passes.csv`); lower passes cross a shorter chord and are shorter.

## 6. Sunlit or in Earth's shadow

The Earth casts a shadow away from the Sun.  The simplest model is a **cylinder** of radius R along the
Earth–Sun line: a satellite is in shadow if it is on the night side (behind the Earth as seen from the Sun) and
less than R from that line.  ⚠ The standard textbook treatment is in Vallado's *Fundamentals of Astrodynamics
and Applications*, chapter on eclipses: read it and cite it.

Skyfield's `is_sunlit` (described in its documentation only as "a simple geometric estimate" [R7]) is used in
the script.  ✓ Because its exact model is not documented, it was checked against the cylinder model on all
3,173 samples: they agree on **99.6 %**, and all 14 disagreements are within 7.2 km of the shadow's edge
(`checks.json`).

**Why satellites are seen after sunset.**  A satellite at height h stays in sunlight until the Sun is about
λ = arccos(R / (R + h)) = **25.6°** below the horizon *for an observer directly beneath it*.  So for well over an
hour after sunset (and before sunrise) the sky can be dark while the satellite overhead is still lit.  Later in
the night it passes into Earth's shadow and fades out, which is what the grey band in the figure shows.

## 7. Is the sky dark? (twilight)

The Sun's position comes from JPL's DE421 ephemeris [R9].  Twilight is defined by how far the **centre of the
Sun** is below the horizon [R10]:

| Sun's elevation | Name |
|---|---|
| 0° to −6° | civil twilight (still bright enough for ordinary outdoor work) |
| −6° to −12° | nautical twilight |
| −12° to −18° | astronomical twilight |
| below −18° | night |

✎ The script counts the sky as **dark** below −6° (the end of civil twilight) and calls a pass **visible** if
at some moment the satellite is above the horizon, sunlit, and the sky is dark.  A stricter choice (−12° or
−18°) would give fewer visible passes.  ⚠ [R10] are secondary sources quoting the US Naval Observatory: find the
USNO's own definitions.

## 8. The Sun angle (phase angle)

At each moment, with vectors from the satellite to the Sun and from the satellite to the observer, cos α =
**s** · **o** (`METHODS_AND_SOURCES.md` §4a).  This is the angle the brightness map is organised by, so it is the
link between these passes and the brightness work (next step).

---

## 9. The figure, panel by panel (`real_passes/AQUA_27424/passes_overview.png`)

**Header.**  TLE epoch and age (§1, §3), observer (§4), the number of passes (24) and visible passes (9)
(§5, §7).  Data: `run_info.json`.

**Top left, "Every pass on the sky."**  Each dot is one 5-s sample: direction = azimuth, distance from the
centre = 90° − elevation (zenith angle), so the centre is straight overhead and the edge is the horizon.
Colour: gold = visible (sunlit, sky dark); blue = sunlit but the sky is too bright; grey = in Earth's shadow.
Data: `samples.csv` columns `azimuth_deg`, `elev_deg`, `sunlit`, `visible`.  **What to notice:** the tracks run
roughly north–south because the orbit is near-polar (98.4°, §1); grey segments are where a satellite fades into
Earth's shadow (§6).

**Top right, "When the passes happen."**  One bar per pass at the time of its highest point; height = highest
elevation; colour as above.  Data: `passes.csv` columns `highest_utc`, `max_elev_deg`, `visible`,
`frac_sunlit`.  **What to notice:** passes come in two groups each day, about 03–07 UTC and 12–18 UTC, because
the orbit is sun-synchronous (§2); only the early-morning group is visible: the afternoon passes are in
daylight.

**Bottom left, "The highest visible pass, moment by moment."**  Pass 10 (30 Oct): elevation (dots, left axis)
and distance (dashed, right axis) against time; grey band = in Earth's shadow.  Data: `samples.csv` for
`pass = 10`.  **What to notice:** distance is smallest (741 km) when elevation is highest (68°), as §4 predicts;
the satellite enters Earth's shadow at 05:17:07 UTC while still 16° up, then disappears (§6).

**Bottom right, "Zenith angle against distance."**  Every sample of every pass; the grey line is the formula of
§4 for the median height (695 km); colour = phase angle (§8).  Data: `samples.csv` columns `elev_deg`,
`range_km`, `height_km`, `phase_deg`.  **What to notice:** the samples sit on the formula (a check of the
geometry); distance is 4.4 times larger at the horizon than overhead; the phase angle varies along the curve,
so the Sun angle and the distance change together during a pass, the "coupled variables" from the last
meeting.

## 10. Checks

1. **Distance formula:** within 5 km (median 1 km) of the full calculation, all 3,173 samples (§4).  ✓
2. **Earth's shadow:** 99.6 % agreement with the cylinder model; differences only at the shadow's edge (§6).  ✓
3. **Independent prediction (Heavens-Above [R11]):** highest point of all six common passes within 2 s and
   0.5°, entry into shadow within 5 s.  Details: `real_passes/AQUA_27424/check_heavens_above.md`.  ✓
4. **Orbit height:** the TLE gives 686–693 km (§2), and the closest approach in the data is 696 km (an 85°
   pass): Aqua is below its 705 km design height [R6], in line with public orbit-tracking data [R12].  ✓
5. **Pass length:** longest pass 13.9 min against 14.0 min from geometry (§5).  ✓

## 11. Every number quoted for step 3, and where it comes from

| Number | Where | How |
|---|---|---|
| 24 passes, 9 visible | `run_info.json` | §5, §7 |
| TLE 0.28 days old | `run_info.json` | window start − TLE epoch (§3) |
| Times 03–07 and 12–18 UTC | `passes.csv` | sun-synchronous orbit (§2) |
| Closest approach 696 km at 85° | `passes.csv`, pass 23 | §4 |
| Height about 690 km | `checks.json` → `orbit` (from the TLE) | §2 |
| 99.6 % shadow agreement | `checks.json` → `shadow` | §6 |
| Within 5 km of the formula | `checks.json` → `distance` | §4 |
| Within 2 s and 0.5° of Heavens-Above | `check_heavens_above.md` | §10 |
| 4.4 times further at the horizon | `samples.csv`; formula | §4 |
| 25.6° (shadow and visibility angle) | `checks.json` → `orbit.horizon_angle_deg` | §5, §6 |
| 14.0 min longest pass | `checks.json` → `orbit` | §5 |
| 1.024° vs 0.9856° per day | `checks.json` → `orbit` | §2 |

All of `checks.json` is made by `python script_code/check_real_pass.py`, so every number above can be
regenerated from the saved TLE.

---

## References

* **[R1]** CelesTrak, current orbital elements (GP data): https://celestrak.org/NORAD/elements/gp.php ; satellite catalogue format: https://celestrak.org/satcat/satcat-format.php
* **[R2]** Hoots, F. R. & Roehrich, R. L. (1980). *Spacetrack Report No. 3: Models for Propagation of NORAD Element Sets.* https://apps.dtic.mil/sti/pdfs/ADA093554.pdf (also https://celestrak.org and AMSAT copies)
* **[R3]** Vallado, D. A., Crawford, P., Hujsak, R. & Kelso, T. S. (2006). *Revisiting Spacetrack Report #3.* AIAA 2006-6753. ⚠ read it
* **[R4]** NASA NSSDCA, *Earth Fact Sheet* (equatorial radius 6,378.137 km, mean radius 6,371.000 km, GM, J₂ = 1082.63 × 10⁻⁶). https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html
* **[R5]** J₂ nodal precession and the sun-synchronous rate (0.9856°/day): *Nodal precession*, https://en.wikipedia.org/wiki/Nodal_precession ; NASA GSFC, *GDC Orbit Primer*, https://science.nasa.gov/wp-content/uploads/2023/05/GDC_OrbitPrimer.pdf ⚠ cite a textbook (e.g. Vallado) for the formula
* **[R6]** NASA, *The Aqua Spacecraft and Instruments* (705 km, 98.8 min, 1:30 pm ascending node). https://science.nasa.gov/mission/aqua/about-aqua-spacecraft-and-instruments/
* **[R7]** Rhodes, B. (2019). *Skyfield.* Astrophysics Source Code Library, ascl:1907.024 (version used: 1.55). Earth-satellite documentation: https://rhodesmill.org/skyfield/earth-satellites.html
* **[R8]** *Dublin City University*, Wikipedia (53°23′06″N 6°15′24″W). https://en.wikipedia.org/wiki/Dublin_City_University
* **[R9]** JPL planetary ephemeris DE421 (Folkner, Williams & Boggs 2008, IPN Progress Report 42-178). ⚠ check the citation
* **[R10]** Twilight definitions (civil −6°, nautical −12°, astronomical −18°, centre of the Sun): PyEphem documentation, *Naval Observatory Risings and Settings*, https://rhodesmill.org/pyephem/rise-set.html ; University of Arizona, *What is Twilight*, https://lavinia.as.arizona.edu/~dmccarthy/GSUSA/activities/0e%20What%20is%20Twilight.pdf ⚠ find the USNO's own page
* **[R11]** Heavens-Above, Aqua passes from DCU. https://www.heavens-above.com/PassSummary.aspx?satid=27424&lat=53.385&lng=-6.2565&loc=DCU&alt=60&tz=UCT
* **[R12]** Orbital Radar, Aqua (27424). https://orbitalradar.com/satellite/27424
