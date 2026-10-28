# Methods and sources

Where every number in the results comes from: the maths behind it, the data and script that produce it, and
the published source for every outside value.  Status marks:

* **✓ checked**: compared against a source or against the data (the check is given)
* **⚠ to check**: the value is used, but you still need to read the source yourself or confirm it
* **✎ our choice**: a decision made for this project, not a fact; state it as an assumption

---

## 1. Measuring brightness in Blender

**What a render pixel holds.**  With the *Standard* view transform and 32-bit OpenEXR output, a pixel value is
linear light: the **radiance** (power per area per solid angle, W m⁻² sr⁻¹) leaving that bit of the satellite
towards the camera.  Colour pixels are turned into one brightness value with the Rec. 709 luminance weights

  Y = 0.2126 R + 0.7152 G + 0.0722 B                                                  ✓ ITU-R BT.709 [6]

**Orthographic camera = parallel rays.**  At orbital range every ray from the satellite to the observer is
effectively parallel, so the scripts use an orthographic camera.  Each pixel then covers the same area,
a = (frame width ÷ pixels)² m², measured square-on to the line of sight.

**Total brightness (the "brightness" column in every CSV).**  Adding radiance × area over the whole picture:

  B = Σ (pixel value × a) = ∫ L dA⊥ = radiant **intensity** towards the observer (W sr⁻¹)

This is the satellite's brightness as a single point of light: the right-hand end of the washout graph.
Code: `_render()` in `script_code/brightness_map.py`, `render_lum()` in `script_code/fidelity_test.py`.

**The Sun lamp.**  Blender's Sun lamp strength is an **irradiance** in W m⁻² (sunlight arriving on a surface
square-on).  All renders use strength E_b = 4.  ✓ Blender manual, *Light Objects* [5].
Its angular size is set to 0.53°, close to the real Sun's 1919″ = 0.533° at 1 AU.  ✓ NASA Sun fact sheet [3]

---

## 2. Checking the renders against theory (calibration)

### 2a. Matte (Lambertian) sphere: checks the absolute brightness

A matte (Lambert) surface scatters light equally in all directions: its radiance is L = ρ E cos i / π, where ρ
is the albedo (reflectivity), E the irradiance and i the angle between the Sun and the surface normal
(Lambert's cosine law).  Adding this up over a lit sphere of radius R gives a standard result [4]:

  I(α) = p · E · R² · Φ(α),  with  p = ⅔ ρ  and  Φ(α) = [sin α + (π − α) cos α] / π     ✓ [4]

* α = **phase angle**: the angle Sun–satellite–observer (0° = Sun behind the observer, "full";
  180° = backlit, "new").
* p = **geometric albedo**: ⅔ of the surface albedo for a Lambert sphere [4].
* Φ(α) = the Lambert phase function, equal to 1 at α = 0 (Russell 1916, as cited in [4]).

**Our numbers:** ρ = 0.8, E = 4, R = √(4/π) = 1.128 m (same face-on area as the 2 × 2 m plate).
At α = 0: theory I = ⅔ × 0.8 × 4 × 1.128² = **2.716**; Blender gives **2.711** (−0.2 %).
Over all 2,124 lit geometries in `brightness_map/data/map_sphere_matte.csv`, measured ÷ theory = 0.998 – 1.007,
mean 0.9994: **agreement within 0.7 %**.  This is what shows that Blender's numbers are physically calibrated.

### 2b. Matte flat plate: checks the angle dependence

A plate of area A with its face at angle i to the Sun and e to the observer has intensity

  I = ρ E A cos i cos e / π    (zero if either cosine is negative: the face is unlit or turned away)

Code: `stats()` in `plots/plot_material_tests.py`.  Result: the measured plate follows this to within
**0.1 % of its peak** (`material_tests/data/summary_stats.json`).  The sphere is constant with spin to within
**0.05 %**, as it should be.

---

## 3. From Blender units to real apparent magnitudes

**Magnitudes** compare brightness on a logarithmic scale: 5 magnitudes = a factor of exactly 100, so one
magnitude = 100^(1/5) ≈ 2.512, and bigger numbers are fainter (Pogson's definition) [7]:

  m₁ − m₂ = −2.5 log₁₀ (F₁ / F₂)

**Derivation.**  Everything in the render is proportional to the Sun's irradiance, so with the real Sun
(irradiance S at 1 AU) instead of E_b, the real intensity is I = (S / E_b) · B.  From a distance d the flux
arriving at the observer is F = I / d² (inverse-square law).  Comparing with the Sun itself, which delivers
flux S and has apparent magnitude m_☉:

  m = m_☉ − 2.5 log₁₀ (F / S) = m_☉ − 2.5 log₁₀ ( B / (E_b · d²) )       (d in metres)

S cancels, so its exact value is not needed; only m_☉ is.

* m_☉ = **−26.74** (V band, at 1 AU).  ✓ NASA Sun fact sheet, "Visual magnitude V(1,0)" [3].
  (Willmer 2018 [1] is the modern reference for the Sun's magnitudes in many filters; it gives the
  *absolute* magnitude M_V = 4.81.  ⚠ Its table also lists apparent magnitudes: check the V value there.)
* For reference, the nominal solar irradiance is S = 1361 W m⁻² (IAU 2015 Resolution B3) [2]; not used.
* Code: `real_mag()` in `plots/plot_brightness_map.py`.

**Example:** Aqua's brightest geometry has B = 20.77 → at d = 1000 km, m = −26.74 − 2.5 log₁₀(20.77 / (4 × 10¹²))
= **1.47**.

**Assumptions:** ✎ grey surfaces (Blender's luminance is used as if it were the V band; real satellites are
coloured, which shifts this by an unknown, probably small, amount) · ✎ no atmosphere · ✎ Sun only (no
Earthshine or moonlight) · ✎ the materials in the NASA models are taken as given.

---

## 4. Geometry

### 4a. Phase angle
With unit vectors **s** (satellite → Sun) and **o** (satellite → observer):  cos α = **s** · **o**.
Code: every script; e.g. `phase_deg` in `brightness_map.py`.

### 4b. Distance to the satellite (slant range) from its elevation
Triangle: Earth's centre, observer (distance R), satellite (distance R + h).  The angle at the observer
between "straight up" and the satellite is 90° + e, where e is the elevation above the horizon.  The cosine
rule, (R + h)² = R² + d² + 2Rd sin e, solved for d:

  d = √[ (R + h)² − (R cos e)² ] − R sin e

| Elevation | Aqua (h = 705 km) | Suomi NPP (h = 824 km) |
|---|---|---|
| 90° (overhead) | 705 km | 824 km |
| 45° | 952 km | 1,105 km |
| 30° | 1,245 km | 1,432 km |
| 20° | 1,593 km | 1,812 km |
| 10° | 2,165 km | 2,415 km |

✓ Check: `dawn_dusk_scenario.py` (an independent vector calculation) gives 2,164 km at 10° elevation.

### 4c. Which way the observer is, seen from the satellite (nadir angle)
Sine rule in the same triangle:  sin η = R cos e / (R + h).  For Aqua at e ≥ 10°: η ≤ **62.5°** from straight
down.  This is the "Earth-pointing" cone in `plots/plot_light_curves.py`.

### 4d. Distance in magnitudes
From the inverse-square law, moving from d₁ to d₂ changes the magnitude by Δm = 5 log₁₀(d₂ / d₁):
1000 → 705 km: −0.76 · 1000 → 1300 km: +0.57 · 1000 → 2200 km: **+1.71**.

### 4e. Orbit period (a check on the constants)
T = 2π √(a³ / GM), a = R + h.  Aqua at 705 km: **98.7 min**; NASA gives 98.8 min [9]  ✓.

---

## 5. Angular size: why "a point of light" is a fair assumption

Small-angle approximation (exact enough for angles this small):

  θ (arcsec) = size ÷ distance × 206,265          (206,265 = arcseconds in one radian = 180 × 3600 / π)

Sizes: the largest extent of each Blender model, `fidelity_test/data/run_info.json`: Aqua 16.7 m,
Suomi NPP 9.05 m.  ✎ This is the largest dimension; the size facing the observer is usually smaller.

| | Overhead | 30° up | 10° up |
|---|---|---|---|
| Aqua | 4.9″ (705 km) | 2.8″ (1,245 km) | 1.6″ (2,165 km) |
| Suomi NPP | 2.3″ (824 km) | 1.3″ (1,432 km) | 0.8″ (2,415 km) |

Compared with:
* the human eye: about **1 arcminute = 60″** (20/20 vision; letters on the 20/20 line have 1′ details) [10]
  → always a point, by a factor of 10 or more;
* atmospheric **seeing**: about **1″** at a good site, 2–4″ at lowland or suburban sites, 0.5–0.7″ median at the
  best observatories [11] → through a telescope, Aqua overhead is a few seeing discs across (a few pixels,
  barely resolved); low down, or for smaller satellites, it is a point.

**Other kinds of satellite, for comparison.**  Sizes are the published deployed spans (tip to tip of the
solar arrays) or, for BlueWalker 3, the square root of its published array area (✎ treating the array as
roughly square).  Distances from the slant-range formula in §4b.

| Satellite | Size | Orbit | Overhead | 30° up | 10° up |
|---|---|---|---|---|---|
| Starlink V2 Mini [18] | 30 m span | ~530 km (Gen2 shells 525–535 km) [18] | 11.7″ | 6.4″ | 3.5″ |
| BlueWalker 3 [17, 19] | √64.4 m² ≈ 8.0 m | ~517 km (508–527 km) [19] | 3.2″ | 1.8″ | 1.0″ |
| Eutelsat 3B, geostationary communications [20] | 31 m span | 35,786 km (GEO) | 0.18″ | 0.17″ | 0.16″ |

From Dublin (latitude 53.4°) a geostationary satellite due south sits at 29° elevation, 38,700 km away: 0.17″.

**Geostationary height, worked out** (not just quoted): a geostationary satellite goes round once per
sidereal day, T = 86,164.1 s.  Kepler's third law, a = (GM T² / 4π²)^⅓ = **42,164 km** from Earth's centre;
minus Earth's equatorial radius 6,378.137 km = **35,786 km**, the standard figure [21].

**So:** to the eye every satellite here is a point (all well under 60″).  Through a telescope, geostationary
communications satellites are always far below the seeing limit: always points.  Large low-orbit satellites
overhead (Starlink V2 Mini at ~12″) are several seeing discs across and would be partly resolved; low down, or
for smaller satellites, they shrink to about the seeing size.  The point-like assumption is safest for
higher orbits, low elevations and smaller satellites, and weakest for large satellites passing overhead.

---

## 6. Our own definitions and settings (✎ state these as assumptions)

| What | Setting | Where |
|---|---|---|
| Sun and observer directions | 48 points spread evenly over the sphere (Fibonacci sphere), ~29° apart → 2,304 geometries | `brightness_map.py` |
| "Look the same" (degeneracy) | same phase angle within ±10° and brightness within ±0.1 mag (≈ 10 %), after removing the object's typical phase curve | `plot_brightness_map.py` |
| Dark | fainter than magnitude 12 | `plot_brightness_map.py` |
| Quoting distance | 1,000 km for the brightness map and spin library; the pass uses its real distance | plot scripts |
| Spin library | 24 axes, 10° steps, phase angles 30°, 90°, 150° | `light_curves.py` |
| Sequence matching | every value within ±0.1 mag, starting spin phase unknown | `plot_light_curves.py` |
| Flicker | median change between neighbouring measurements, per 10 s | `plot_light_curves.py` |
| Slow spin / tumble | 0.8°/s about the satellite's up axis / 6°/s about a tilted axis (1,1,1) | `light_curves.py` |
| Dawn-dusk pass | circular orbit at 705 km, β = 85°, observer where the Sun is 4° below the horizon, Earth's rotation and shadow ignored | `dawn_dusk_scenario.py` |
| Simple shapes | grey, albedo 0.8; shiny = metallic, roughness 0.15 | `brightness_map.py`, `material_tests.py` |
| Renderer | EEVEE, 256–512 px, 16 samples | all |

---

## 7. Outside values used

| Value | Used | Source | Status |
|---|---|---|---|
| Sun's apparent V magnitude | −26.74 | NASA Sun fact sheet [3] | ✓ |
| Sun's angular diameter | 1919″ (0.533°) at 1 AU | NASA Sun fact sheet [3] | ✓ |
| Solar irradiance | 1361 W m⁻² (not needed: it cancels) | IAU 2015 B3 [2] | ✓ |
| Earth's mean radius | 6,371.000 km | NASA Earth fact sheet [8] | ✓ |
| Earth's GM | 398,600 km³ s⁻² (script uses 398,600.4418) | NASA Earth fact sheet [8] | ✓ |
| Lambert sphere law, p = ⅔ρ | see §2a | [4] | ✓ (read the cited papers) |
| Magnitude definition | 5 mag = ×100 | Pogson 1856 [7] | ⚠ find the original or a textbook |
| Luminance weights | 0.2126, 0.7152, 0.0722 | ITU-R BT.709-6 [6] | ✓ |
| Blender Sun strength unit | W m⁻² irradiance | Blender manual [5] | ✓ |
| Aqua orbit | 705 km, 98.8 min (design) | NASA [9] | ✓ but see note below |
| Suomi NPP orbit | 824 km (nominal) | eoPortal [12] | ✓ but see note below |
| Eye resolution | ~1′ | EyeWiki [10] | ⚠ find a textbook source |
| Seeing | ~1″ good site | [11] | ⚠ quote a real site's measurements |
| Naked-eye limit | ~6 mag | [13] | ⚠ Schaefer (1993) is the primary source |
| Polaris | V = 1.98 (1.86 – 2.13, it varies) | Wikipedia, citing SIMBAD [14] | ⚠ check SIMBAD directly |
| 3D models | Aqua, Suomi NPP | NASA 3D Resources [15] | ⚠ add the exact file links; the README says "free and without copyright", see NASA's media usage guidelines |

**Notes on the orbits.**  705 km and 824 km are the **nominal design** values.  Aqua's orbit has since been
lowered: current orbit data put it near **686 km** (period ≈ 98.5 min) [16].  Suomi NPP's measured mean
altitude has been about **834 – 839 km** [12].  The results so far use the nominal values; the real-orbit
work should take current orbits from CelesTrak.

---

## 8. Not modelled yet (in the planned order)

Real orbit and observer → horizon → zenith angle vs distance → Earth's shadow (eclipse) → atmosphere
(extinction grows with airmass, roughly 1 / cos(zenith angle)) → measurement noise.  ⚠ Each needs its own
source when added.

---

## References

1. Willmer, C. N. A. (2018). *The Absolute Magnitude of the Sun in Several Filters.* ApJS. doi:10.3847/1538-4365/aabfdf · https://arxiv.org/abs/1804.07788
2. Prša, A. et al. (2016). *Nominal values for selected solar and planetary quantities: IAU 2015 Resolution B3.* AJ 152, 41. https://arxiv.org/abs/1605.09788
3. NASA NSSDCA, *Sun Fact Sheet.* https://nssdc.gsfc.nasa.gov/planetary/factsheet/sunfact.html
4. Lambert-sphere phase function and albedos: Seager, Whitney & Sasselov (2000), https://arxiv.org/abs/astro-ph/0004001 ; Madhusudhan & Burrows (2012), https://arxiv.org/abs/1112.4476 (both cite Russell 1916 for Φ(α)).
5. Blender Manual, *Light Objects* (Sun: strength in W/m²). https://docs.blender.org/manual/en/latest/render/lights/light_object.html
6. ITU-R Recommendation BT.709. https://www.itu.int/rec/R-REC-BT.709
7. Pogson, N. (1856), magnitude scale; summary: Britannica, *Photometry (astronomy).* https://www.britannica.com/science/photometry-astronomy
8. NASA NSSDCA, *Earth Fact Sheet.* https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html
9. NASA, *The Aqua Spacecraft and Instruments.* https://science.nasa.gov/mission/aqua/about-aqua-spacecraft-and-instruments/
10. EyeWiki, *Visual Acuity Testing in Adults.* https://eyewiki.org/Visual_Acuity_Testing_in_Adults
11. Instituto de Astrofísica de Canarias, *Seeing* (site quality). https://iac.edu.es/en/observatorios-de-canarias/sky-quality/sky-quality-parameters/seeing ; overview: https://en.wikipedia.org/wiki/Astronomical_seeing
12. eoPortal, *Suomi NPP.* https://eoportal.org/satellite-missions/suomi-npp
13. *Limiting magnitude* overview: https://en.wikipedia.org/wiki/Limiting_magnitude (primary: Schaefer 1993, Vistas in Astronomy)
14. *Polaris*: https://en.wikipedia.org/wiki/Polaris (SIMBAD: https://simbad.u-strasbg.fr/)
15. NASA 3D Resources. https://github.com/nasa/NASA-3D-Resources · https://science.nasa.gov/3d-resources/
16. Orbital Radar, Aqua (NORAD 27424), based on public orbit data. https://orbitalradar.com/satellite/27424
17. Related observations: Nandakumar, S. et al. (2023). *The high optical brightness of the BlueWalker 3 satellite.* Nature 623, 938–941. doi:10.1038/s41586-023-06672-7
18. Spaceflight Now (2023), *SpaceX unveils first batch of larger upgraded Starlink satellites* (V2 Mini: ~30 m span, 116 m² arrays; Gen2 altitudes 525–535 km from the FCC authorisation). https://spaceflightnow.com/2023/02/26/spacex-unveils-first-batch-of-larger-upgraded-starlink-satellites/  ⚠ secondary source: look for the FCC filing.
19. AST SpaceMobile press release (2022), BlueWalker 3 array 693 ft² (64.4 m²). https://www.businesswire.com/news/home/20220908005651/en ; altitude 508–527 km (Nov 2022) from the BlueWalker 3 Wikipedia entry ⚠ check against current orbit data.
20. Spaceflight101, *Eutelsat 3B* (Eurostar-3000: 7.5 m high, 31 m span). https://spaceflight101.com/spacecraft/?p=1644  ⚠ secondary source: check Airbus or Eutelsat.
21. American Meteorological Society, *Glossary of Meteorology: geostationary satellite* (35,786 km above the equator). https://glossarytest.ametsoc.net/wiki/Geostationary_satellites
