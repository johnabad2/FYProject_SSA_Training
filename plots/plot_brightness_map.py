"""
plot_brightness_map.py - the graphs for the brightness map (every Sun direction x every observer direction).

  python plot_brightness_map.py [repo folder]        (default: the folder above this script)

Reads   brightness_map/data/map_*.csv, objects.json   (made by brightness_map.py in Blender)
Writes  brightness_map/brightness_map_satellites.png  range, phase dependence, one sky map, degeneracy
        brightness_map/brightness_map_shapes.png      the same brightness-vs-phase view for each simple shape
        brightness_map/data/summary_stats.json        the numbers quoted
Needs Python with numpy and matplotlib.  Run it outside Blender (any Python).

Magnitudes are real apparent magnitudes, as seen from REF_RANGE_KM away, with no atmosphere.  The renders are
physically calibrated: brightness (pixel luminance x pixel area) is the intensity for a Sun of strength E_BLENDER,
checked against the textbook Lambert sphere to within 0.7%.  With the real Sun instead:
    m = M_SUN - 2.5 log10( brightness / (E_BLENDER x range^2) )        (range in metres)
Bigger m = fainter; 1 magnitude = x2.5; the naked-eye limit is about 6.  Colour is ignored (grey surfaces).
Geometries fainter than DARK_MAG are counted as dark and drawn at that floor.

Degeneracy ("how many orientations look the same"): for every geometry, take all geometries with nearly the
same phase angle (within PHASE_TOL degrees, as if the phase were known from the orbit) and count the share
whose brightness, after taking out the object's typical change with phase, is within MAG_TOL magnitudes
(about 10%).  1 = every orientation looks the same (a sphere);
close to 0 = the brightness pins down the orientation.
"""
import csv
import json
import math
import os
import shutil
import sys
import tempfile

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
D = os.path.join(ROOT, "brightness_map", "data") + os.sep
OUT = os.path.join(ROOT, "brightness_map")
M_SUN = -26.74           # the Sun's apparent (V) magnitude at 1 AU
E_BLENDER = 4.0          # Sun lamp strength in the renders (SUN_STRENGTH in brightness_map.py / light_curves.py)
REF_RANGE_KM = 1000.0    # distance the magnitudes are quoted at (a common standard for low Earth orbit)
NAKED_EYE = 6.0          # faintest magnitude the eye sees in a dark sky
DARK_MAG = 12.0          # fainter than this = dark (about 10 magnitudes below Aqua's brightest)
PHASE_TOL = 10.0         # degrees
MAG_TOL = 0.1            # magnitudes, about 10% in brightness
BINS = np.arange(0, 181, 10)

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COL = {"A": "#2a78d6", "C": "#eb6834"}
SHAPE_ORDER = ["sphere_matte", "plate_matte", "plate_shiny", "cube_matte", "cylinder_matte", "boxwing_matte"]


def _write(dest, saver):
    """Save via a temp file, then copy over: writing straight onto an existing file can fail on some mounted drives."""
    tmp = os.path.join(tempfile.gettempdir(), "_plot_tmp_" + os.path.basename(dest))
    saver(tmp)
    shutil.copyfile(tmp, dest)
    os.remove(tmp)


def real_mag(brightness, range_km=REF_RANGE_KM):
    """Apparent magnitude seen from range_km away (see the docstring); clipped at DARK_MAG."""
    d = np.asarray(range_km, float) * 1000.0
    m = M_SUN - 2.5 * np.log10(np.maximum(np.asarray(brightness, float), 1e-30) / (E_BLENDER * d * d))
    return np.minimum(m, DARK_MAG)


def load():
    info = json.load(open(D + "objects.json")) if os.path.exists(D + "objects.json") else {}
    n = json.load(open(D + "directions.json"))["n"]
    data = {}
    for key in ["A", "C"] + SHAPE_ORDER:
        p = D + f"map_{key}.csv"
        if not os.path.exists(p):
            continue
        rows = list(csv.DictReader(open(p)))
        a = {k: np.array([float(r[k]) for r in rows]) for k in ("sun_i", "obs_i", "phase_deg", "brightness",
                                                                "obs_x", "obs_y", "obs_z", "sun_x", "sun_y", "sun_z")}
        a["complete"] = len(rows) == n * n
        a["label"] = info.get(key, {}).get("label", key)
        data[key] = a
    if not data:
        sys.exit(f"No brightness-map data in {D}: run brightness_map.py in Blender first.")
    for a in data.values():
        a["mag"] = real_mag(a["brightness"])
        a["dark"] = a["mag"] >= DARK_MAG - 1e-9
    return data, n


def phase_residual(a):
    """Magnitude minus the object's typical (median) phase curve: what is left is due to orientation."""
    centres = (BINS[:-1] + BINS[1:]) / 2
    med = by_phase(a["phase_deg"], a["mag"], 50)
    ok = ~np.isnan(med)
    return a["mag"] - np.interp(a["phase_deg"], centres[ok], med[ok])


def degeneracy(a):
    """Share of same-phase geometries whose brightness matches each geometry (see the docstring).

    The object's typical phase curve (median per phase bin) is taken out first, so the change of brightness
    with phase inside the +-PHASE_TOL window is not mistaken for a difference between orientations.
    Two dark geometries always match."""
    ph, dark = a["phase_deg"], a["dark"]
    resid = phase_residual(a)
    out = np.empty(len(ph))
    for s in range(0, len(ph), 512):                      # in chunks to keep memory small
        e = slice(s, s + 512)
        near = np.abs(ph[e, None] - ph[None, :]) <= PHASE_TOL
        both_dark = dark[e, None] & dark[None, :]
        both_lit = ~dark[e, None] & ~dark[None, :]
        same = near & (both_dark | (both_lit & (np.abs(resid[e, None] - resid[None, :]) <= MAG_TOL)))
        out[e] = same.sum(1) / near.sum(1)
    return out


def by_phase(ph, v, q):
    """Percentile q of v in each phase bin (nan where a bin is empty)."""
    idx = np.digitize(ph, BINS) - 1
    return np.array([np.percentile(v[idx == b], q) if np.any(idx == b) else np.nan for b in range(len(BINS) - 1)])


def stats(data):
    out = {}
    centres = (BINS[:-1] + BINS[1:]) / 2
    for key, a in data.items():
        lit = ~a["dark"]
        deg = degeneracy(a)
        a["deg"] = deg
        a["resid"] = phase_residual(a)
        spread = by_phase(a["phase_deg"], a["resid"], 90) - by_phase(a["phase_deg"], a["resid"], 10)
        out[key] = {"label": a["label"], "geometries": int(len(a["mag"])), "complete": bool(a["complete"]),
                    "brightest_mag": float(a["mag"].min()),
                    "median_mag_lit": float(np.median(a["mag"][lit])) if lit.any() else None,
                    "faintest_lit_mag": float(a["mag"][lit].max()) if lit.any() else None,
                    "range_p5_p95_mag": float(np.percentile(a["mag"][lit], 95) - np.percentile(a["mag"][lit], 5)) if lit.any() else None,
                    "frac_dark": float(a["dark"].mean()),
                    "frac_naked_eye": float((a["mag"] <= NAKED_EYE).mean()),
                    "mag_percentiles_5_25_50_75_95": [round(float(v), 2) for v in np.percentile(a["mag"], [5, 25, 50, 75, 95])],
                    "frac_brighter_than_mag": {str(m): round(float((a["mag"] <= m).mean()), 3) for m in (2, 3, 4, 6, 8, 10)},
                    "mag_by_phase_range_median_p10_p90": {
                        f"{lo}-{min(hi, 180)}": [round(float(np.percentile(a["mag"][sel], q)), 2) for q in (50, 10, 90)]
                        for lo, hi in ((0, 45), (45, 90), (90, 120), (120, 150), (150, 181))
                        for sel in [(a["phase_deg"] >= lo) & (a["phase_deg"] < hi)] if sel.any()},
                    "median_spread_at_fixed_phase_mag": float(np.nanmedian(spread)),
                    "spread_by_phase_mag": {f"{c:.0f}": (None if np.isnan(s) else round(float(s), 3)) for c, s in zip(centres, spread)},
                    "median_degeneracy": float(np.median(deg)),
                    "median_degeneracy_lit": float(np.median(deg[lit])) if lit.any() else None}
    json.dump(out, open(D + "summary_stats.json", "w"), indent=1)
    for k, s in out.items():
        print(f"{k:15s} dark {s['frac_dark']:.2f}  p5-p95 range {s['range_p5_p95_mag']}  spread@phase {s['median_spread_at_fixed_phase_mag']:.2f} mag  "
              f"degeneracy {s['median_degeneracy']:.2f}" + ("" if s["complete"] else "   (incomplete)"))
    return out


def _style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.facecolor": SURF,
                         "figure.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})


def _grid(ax):
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)


def _title(ax, head, sub):
    ax.set_title(head, loc="left", fontsize=13, fontweight="bold", color=INK, pad=26)
    ax.text(0, 1.025, sub, transform=ax.transAxes, fontsize=9.8, color=INK2, va="bottom")


def _phase_axis(ax):
    ax.set_xlim(0, 180); ax.set_xticks(range(0, 181, 30)); ax.set_xlabel("phase angle: Sun–satellite–observer (degrees)")


def _mag_axis(ax, lo, hi):
    ax.set_ylim(hi, lo); ax.set_ylabel(f"apparent magnitude at {REF_RANGE_KM:,.0f} km  (up = brighter)")
    ax.axhline(NAKED_EYE, color="#b9b8b0", lw=1.1)
    ax.text(178, NAKED_EYE - 0.15, "naked-eye limit", ha="right", va="bottom", fontsize=9, color=INK2)


def satellites_figure(data, st, n):
    sats = [k for k in ("A", "C") if k in data]
    if not sats:
        print("no satellite data yet: skipping brightness_map_satellites.png")
        return
    _style()
    allm = np.concatenate([data[k]["mag"] for k in sats])
    lo, hi = math.floor(allm.min()) - 0.3, DARK_MAG + 0.6
    centres = (BINS[:-1] + BINS[1:]) / 2
    fig = plt.figure(figsize=(16, 9.6))
    gs = fig.add_gridspec(2, 2, hspace=0.6, wspace=0.22, left=0.06, right=0.975, top=0.815, bottom=0.07)
    fig.text(0.06, 0.955, "How bright does each satellite look, for every Sun and observer direction?", fontsize=17, fontweight="bold", color=INK)
    fig.text(0.06, 0.928, f"Ideal conditions: one Sun, black sky, no noise.  {n} Sun directions × {n} observer directions spread over the sphere "
             f"(≈{math.degrees(math.sqrt(4 * math.pi / n)):.0f}° apart), each seen as a single point of light.\n"
             f"Real apparent magnitudes as seen from {REF_RANGE_KM:,.0f} km, no atmosphere.  Points on the dashed floor are dark "
             f"(fainter than magnitude {DARK_MAG:.0f}).", fontsize=9.8, color=INK2, va="top")

    # (a) brightness vs phase
    ax = fig.add_subplot(gs[0, 0]); _grid(ax)
    for k in sats:
        a = data[k]
        ax.scatter(a["phase_deg"], a["mag"], s=4, color=COL[k], alpha=0.12, lw=0)
        ax.plot(centres, by_phase(a["phase_deg"], a["mag"], 50), color=COL[k], lw=2.4, label=a["label"])
    ax.axhline(DARK_MAG, color=INK2, lw=0.9, ls=(0, (4, 3)))
    _phase_axis(ax); _mag_axis(ax, lo, hi)
    ax.legend(loc="lower left", frameon=False, fontsize=10)
    _title(ax, "Brightness against phase angle", "dots: every geometry; line: median.  The vertical spread at one phase angle is due to orientation alone")

    # (b) spread at fixed phase
    ax = fig.add_subplot(gs[0, 1]); _grid(ax)
    for k in sats:
        a = data[k]
        p10, p90 = by_phase(a["phase_deg"], a["resid"], 10), by_phase(a["phase_deg"], a["resid"], 90)
        ax.plot(centres, p90 - p10, color=COL[k], lw=2.4, marker="o", ms=5, mec=SURF, label=a["label"])
    _phase_axis(ax); ax.set_ylabel("spread, 10th–90th percentile (magnitudes)"); ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    _title(ax, "How much orientation changes the brightness", "at a fixed phase angle; 2.5 mag = a factor of 10 in brightness")

    # (c) one sky map
    k = sats[0]; a = data[k]
    ax = fig.add_subplot(gs[1, 0]); _grid(ax)
    lit_by_sun = [np.mean(~a["dark"][a["sun_i"] == i]) for i in range(n)]
    si = int(np.argmax(lit_by_sun))                        # the Sun direction that lights the most views
    m = a["sun_i"] == si
    az = np.degrees(np.arctan2(a["obs_y"][m], a["obs_x"][m])) % 360
    el = np.degrees(np.arcsin(np.clip(a["obs_z"][m], -1, 1)))
    sc = ax.scatter(az, el, c=a["mag"][m], cmap="viridis_r", vmin=lo, vmax=DARK_MAG, s=150, edgecolor=SURF, lw=0.8, zorder=3)
    s = np.array([a["sun_x"][m][0], a["sun_y"][m][0], a["sun_z"][m][0]])
    ax.plot(math.degrees(math.atan2(s[1], s[0])) % 360, math.degrees(math.asin(np.clip(s[2], -1, 1))), marker="*", ms=22,
            color="#eda100", mec=INK, mew=0.8, zorder=4, ls="")
    cb = fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.04); cb.ax.invert_yaxis(); cb.set_label(f"apparent magnitude at {REF_RANGE_KM:,.0f} km", color=INK2)
    cb.outline.set_visible(False)
    ax.set_xlim(-5, 365); ax.set_ylim(-95, 95); ax.set_xticks(range(0, 361, 60)); ax.set_yticks(range(-90, 91, 30))
    ax.set_xlabel("observer azimuth, seen from the satellite (degrees)"); ax.set_ylabel("observer elevation (degrees)")
    _title(ax, f"{a['label']}: one Sun direction, every observer direction",
           "star = Sun.  Each dot is where an observer could be; its colour is the brightness they would see")

    # (d) degeneracy
    ax = fig.add_subplot(gs[1, 1]); _grid(ax)
    for k in sats:
        a = data[k]
        ax.plot(centres, by_phase(a["phase_deg"], a["deg"], 50) * 100, color=COL[k], lw=2.4, marker="o", ms=5, mec=SURF, label=a["label"])
    for key, ls in (("sphere_matte", (0, (4, 3))), ("plate_matte", (0, (1, 2)))):
        if key in data:
            ax.plot(centres, by_phase(data[key]["phase_deg"], data[key]["deg"], 50) * 100, color=INK2, lw=1.4, ls=ls, label=data[key]["label"])
    _phase_axis(ax); ax.set_ylim(0, 105); ax.set_ylabel("orientations that look the same (%)")
    ax.legend(loc="center left", frameon=False, fontsize=9.5)
    _title(ax, "Degeneracy: how often different orientations look identical",
           f"share of same-phase (±{PHASE_TOL:.0f}°) geometries within ±{MAG_TOL} mag (≈10%) of each other")
    if not all(data[k]["complete"] for k in sats):
        fig.text(0.975, 0.955, "PARTIAL DATA: brightness_map.py has not finished", ha="right", fontsize=11, fontweight="bold", color="#c0392b")
    out = os.path.join(OUT, "brightness_map_satellites.png")
    _write(out, lambda p: fig.savefig(p, dpi=130, facecolor=SURF)); plt.close(fig)
    print("saved", out)


def shapes_figure(data, st):
    shapes = [k for k in SHAPE_ORDER if k in data]
    if not shapes:
        print("no shape data yet: skipping brightness_map_shapes.png")
        return
    _style()
    allm = np.concatenate([data[k]["mag"] for k in shapes])
    lo, hi = math.floor(allm.min()) - 0.3, DARK_MAG + 0.6
    centres = (BINS[:-1] + BINS[1:]) / 2
    cols = 3; rows = math.ceil(len(shapes) / cols)
    h = 4.6 * rows + 2.0                                   # inches: panels + heading + axis labels
    fig = plt.figure(figsize=(16, h))
    gs = fig.add_gridspec(rows, cols, hspace=0.75, wspace=0.22, left=0.06, right=0.975, top=1 - 1.75 / h, bottom=0.7 / h)
    fig.text(0.06, 1 - 0.4 / h, "Simple shapes: brightness against phase angle for every orientation",
             fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 1 - 0.85 / h, "Same method as the satellites.  A tall cloud of dots at one phase angle means the orientation "
             "changes the brightness a lot;\na thin line means it does not (that shape's orientation cannot be told from its brightness).",
             fontsize=9.8, color=INK2, va="top")
    for n_, key in enumerate(shapes):
        a = data[key]; s = st[key]
        ax = fig.add_subplot(gs[n_ // cols, n_ % cols]); _grid(ax)
        ax.scatter(a["phase_deg"], a["mag"], s=4, color="#2a78d6", alpha=0.15, lw=0)
        ax.plot(centres, by_phase(a["phase_deg"], a["mag"], 50), color=INK, lw=1.8)
        ax.axhline(DARK_MAG, color=INK2, lw=0.9, ls=(0, (4, 3)))
        _phase_axis(ax); _mag_axis(ax, lo, hi)
        if n_ % cols:
            ax.set_ylabel("")
        _title(ax, a["label"], f"spread {s['median_spread_at_fixed_phase_mag']:.1f} mag · dark {s['frac_dark'] * 100:.0f}% · "
                               f"look-alike {s['median_degeneracy'] * 100:.0f}%" + ("" if a["complete"] else " · PARTIAL"))
    out = os.path.join(OUT, "brightness_map_shapes.png")
    _write(out, lambda p: fig.savefig(p, dpi=120, facecolor=SURF)); plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    data, n = load()
    st = stats(data)
    satellites_figure(data, st, n)
    shapes_figure(data, st)
