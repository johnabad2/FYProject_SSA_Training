# The ideal case: how a satellite's brightness depends on lighting and viewing angle

Write-up of the first stage of the project.  The maths and every outside source are in
`METHODS_AND_SOURCES.md` (section numbers below refer to it); every result comes from a file named in
**[brackets]**, made by the scripts listed in `CODE_GUIDE.md` (this folder).

## 1. Aim

From the ground, a satellite in low Earth orbit is a point of light, so its brightness over time is the main
thing an observer measures.  That brightness depends on where the Sun is, where the observer is, and how the
satellite is oriented.  This stage asks, under ideal conditions:

1. how bright a satellite looks, and over what range, for every combination of lighting and viewing angle;
2. how much the orientation alone changes the brightness;
3. how often different orientations give the same brightness (degeneracy), and whether a sequence of
   measurements removes that;
4. whether a stable satellite can be told from a tumbling one.

**Ideal conditions** means: the Sun as the only light source (no Earthshine or moonlight), no atmosphere, no
measurement noise, and the satellite treated as a single point of light.

## 2. Is a single point of light justified?

Angular size = size ÷ distance × 206,265 arcseconds (§5).  Aqua (16.7 m) is 4.9″ overhead and 1.6″ at 10°
elevation; Suomi NPP (9.05 m) is 2.3″ and 0.8″.  The eye resolves about 60″ and the atmosphere blurs a
telescope image to about 1″ at a good site.  So to the eye both are always points; through a telescope they are
at most a few seeing discs across overhead and essentially points low down.  For comparison, a geostationary
communications satellite (31 m) is about 0.17″, always a point, while a large Starlink V2 Mini (30 m span) is
about 12″ overhead and would be partly resolved by a telescope.  The point-of-light assumption is therefore
reasonable for these two satellites, and is weakest for large satellites passing overhead.

## 3. Method

* **Models:** NASA 3D Resources models of Aqua (detailed, 115,142 triangles) and Suomi NPP (low-poly, 4,024
  triangles), rendered in Blender 5.2 (EEVEE) with one Sun lamp and a black sky.
* **Measurement:** an orthographic camera (parallel rays, as at orbital range); brightness = the sum of linear
  pixel luminance × pixel area = the satellite's intensity towards the observer (§1).
* **Calibration:** a matte sphere rendered the same way matches the textbook Lambert-sphere brightness to within
  **0.7 %** at every angle (2,124 geometries) **[brightness_map/data/map_sphere_matte.csv]**, and a matte plate
  follows Lambert's cosine law to within **0.1 %** of its peak **[material_tests/data/summary_stats.json]** (§2).
* **Real magnitudes:** m = −26.74 − 2.5 log₁₀(B / (E_b d²)), quoted at d = 1,000 km unless stated (§3).
* **Brightness map:** every combination of 48 Sun directions × 48 observer directions spread evenly over the
  sphere (2,304 geometries per object, about 29° apart), for both satellites and six simple shapes
  **[brightness_map/data/]**.
* **Light curves:** each satellite spun through 360° about 24 different axes in 10° steps, at Sun–observer
  angles of 30°, 90° and 150° **[light_curves/data/spin_*.csv]**; and a simplified dawn-dusk pass (705 km
  orbit, 8.3 min, mostly backlit) rendered stable, slowly spinning (0.8°/s) and tumbling (6°/s)
  **[light_curves/data/pass_*.csv]**.

## 4. Results

### 4.1 Earlier tests (material and model detail)

* **Surfaces** **[material_tests/data/summary_stats.json]**: a matte sphere's brightness does not change with
  orientation (within 0.05 %); a matte plate is bright over 41 % of a turn and dark over 34 %; a shiny panel is
  nearly dark except for two glints about **1,200 times** the sphere's brightness, each only **1.6°** of rotation
  wide.  Brightness falls with distance with a fitted slope of −2.01, matching the inverse-square law.
* **Model detail** **[fidelity_test/data/summary_stats.json]**: simplified versions of Aqua stay wrong even as a
  single point of light.  A plain automatic reduction to 4k triangles is 70–90 % off; reductions that keep
  the flat panels whole are 2–12 % off at 30k triangles on the spins (46 % on the backlit dawn-dusk pass) and up
  to 100 % off at 4–5k, because simplifying
  shrinks the thin solar panels and loses reflecting area.  **The detailed model is used for everything below.**

### 4.2 Range of brightness **[brightness_map/data/summary_stats.json]**

At 1,000 km, Aqua ranges from **magnitude 1.5** (about as bright as Polaris) to about **12** (telescope only),
a factor of about 16,000.  Half of all geometries lie between **3.5 and 6.2** (median **4.4**); Aqua is
brighter than magnitude 6 (the naked-eye limit) in **74 %** of geometries, brighter than 3 in only **12 %**,
and fainter than 10 in **5 %**.  Suomi NPP is smaller and about a magnitude fainter: brightest **2.6**, middle
half **4.6–6.4**, median **5.4**, naked-eye visible in **67 %**.

### 4.3 What drives the range

1. **Phase angle (Sun–satellite–observer) — the largest effect.**  Aqua's median magnitude goes from **3.1** at
   0–45° to **3.8** (45–90°), **5.1** (90–120°), **7.3** (120–150°) and **10.3** (150–180°): about 7 magnitudes,
   a factor of about 750, from lit-from-behind-the-observer to backlit, like the Moon's phases.
2. **Orientation.**  At a fixed phase angle, turning the satellite changes the brightness by a median of
   **2.4 magnitudes** (10th–90th percentile; about ×10) for Aqua and **2.2** for Suomi NPP, rising to **4–5
   magnitudes** when backlit, where only a few surfaces catch the light.
3. **Distance** — smaller: going from 1,000 to 2,200 km (a low pass) makes it **1.7 magnitudes** fainter (§4d).

### 4.4 Degeneracy from a single snapshot

Treating two geometries as "the same" when their phase angles are within ±10° and their brightness within
±0.1 mag (≈ 10 %), a single measurement matches a median of **5.7 %** of other orientations for both
satellites.  So one snapshot rules out most orientations but not all: the degeneracy is real but limited.
For comparison, a matte sphere is **100 %** degenerate (it looks the same whichever way it faces), a flat plate
15 %, a cube 21 %, a cylinder 18 % and a box with one solar wing 9 %
**[brightness_map/data/summary_stats.json]**.  The box-wing is the simple shape closest to the real satellites.

### 4.5 A sequence of measurements **[light_curves/data/summary_stats.json]**

Comparing stretches of light curve between the 24 spin axes (with the starting point unknown):

| Measurements in a row (10° of spin apart) | 1 | 2 | 3 | 6 | 12 |
|---|---|---|---|---|---|
| Aqua, Sun 30° from observer: other axes that match | 81 % | 65 % | 45 % | 12 % | 0.8 % |
| Aqua, 90° | 80 % | 25 % | 9 % | 0.5 % | 0 % |
| Aqua, 150° | 66 % | 7 % | 0.6 % | 0 % | 0 % |
| Suomi NPP, 90° | 77 % | 26 % | 11 % | 0.6 % | 0 % |

Over a full turn, **none of the 276 pairs of axes** give the same light curve (closest rms difference: median
0.9 mag).  So under ideal conditions **a short sequence — about 6 measurements, or 12 when the satellite is lit
from behind the observer — mostly removes the degeneracy** that a single snapshot leaves.

### 4.6 Stable versus tumbling on a pass **[light_curves/data/summary_stats.json]**

At the pass's real distance (1,280–2,160 km):

| | Stable (Earth-pointing) | Slow spin (0.8°/s) | Tumbling (6°/s) |
|---|---|---|---|
| Aqua: min / median / max magnitude | 3.5 / 8.8 / 9.5 | 5.4 / 9.2 / 10.6 | 3.6 / 7.7 / 11.8 |
| Typical change, mag per 10 s (Aqua / Suomi NPP) | 0.06 / 0.06 | 0.44 / 0.36 | 2.7 / 3.1 |

Stable and tumbling differ by a factor of about 50 in how fast the brightness changes, so they are easy to tell
apart.  A stable Aqua sits around magnitude 9 (binoculars or a small telescope) but shows a few one-frame
**glints** up to magnitude 3.5 from its shiny parts: **a single flash does not mean a satellite is tumbling;
regular, repeated flicker does.**  Knowing that a satellite is Earth-pointing rules out 73 % of the geometries
(624 of 2,304 remain).

## 5. Assumptions and limitations

* Sun only (no Earthshine or moonlight); no atmosphere; no measurement noise.
* EEVEE renderer only (not yet checked against Cycles); grey-surface assumption when converting to the V band.
* Directions about 29° apart: narrow glints are often missed (the shiny plate is dark 79 % of the time partly
  for this reason).
* Single point of light only, not few-pixel images.
* Nominal orbits (Aqua 705 km, Suomi NPP 824 km); Aqua's real orbit has since been lowered to about 686 km.
* The dawn-dusk pass is simplified (Earth's rotation and shadow ignored).
* The settings listed in §6 of `METHODS_AND_SOURCES.md` (grid, tolerances, spin rates) are choices, not facts.

## 6. Next

Put the satellite on a real orbit over a real observer and step through time, so that distance, elevation,
phase angle and Earth's shadow all follow from the orbit; then add the horizon, zenith angle against distance,
and Earth's shadow; then the atmosphere and measurement noise.
