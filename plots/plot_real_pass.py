"""
plot_real_pass.py - the graphs for real_pass.py: a real satellite's passes over a real observer.

  python plots/plot_real_pass.py [folder]      (default: every folder in real_passes/)

Reads   real_passes/<NAME>_<number>/passes.csv, samples.csv, run_info.json   (made by real_pass.py)
Writes  real_passes/<NAME>_<number>/passes_overview.png
Needs Python with numpy and matplotlib.

Panels: every pass drawn on the sky; when the passes happen and how high they get; the best visible pass over
time (elevation, distance, Earth's shadow); and zenith angle against distance for every sample, with the
spherical-Earth formula from docs/METHODS_AND_SOURCES.md section 4b drawn on top as a check.
"""
import csv
import datetime as dt
import glob
import json
import os
import shutil
import sys
import tempfile

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
VIS, LIT, SHADOW = "#eda100", "#2a78d6", "#b9b8b0"      # visible / sunlit but sky too bright / in Earth's shadow
R_EARTH = 6371.0


def _write(dest, saver):
    """Save via a temp file, then copy over: writing straight onto an existing file can fail on some mounted drives."""
    tmp = os.path.join(tempfile.gettempdir(), "_plot_tmp_" + os.path.basename(dest))
    saver(tmp)
    shutil.copyfile(tmp, dest)
    os.remove(tmp)


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(folder):
    info = json.load(open(os.path.join(folder, "run_info.json")))
    passes = list(csv.DictReader(open(os.path.join(folder, "passes.csv"))))
    rows = list(csv.DictReader(open(os.path.join(folder, "samples.csv"))))
    s = {k: np.array([float(r[k]) for r in rows]) for k in
         ("pass", "seconds_from_rise", "elev_deg", "azimuth_deg", "range_km", "height_km", "sunlit", "sun_elev_deg",
          "phase_deg", "sky_dark", "visible")}
    s["time"] = np.array([_t(r["time_utc"]) for r in rows])
    return info, passes, s


def _state(s, m):
    """Colour for each sample: visible, sunlit in a bright sky, or in Earth's shadow."""
    return np.where(s["visible"][m] > 0, VIS, np.where(s["sunlit"][m] > 0, LIT, SHADOW))


def _title(ax, head, sub, pad=26):
    ax.set_title(head, loc="left", fontsize=13, fontweight="bold", color=INK, pad=pad)
    ax.text(0, 1.025 if pad == 26 else 1.085, sub, transform=ax.transAxes, fontsize=9.8, color=INK2, va="bottom")


def _grid(ax):
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)


def figure(folder):
    info, passes, s = load(folder)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.facecolor": SURF,
                         "figure.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(2, 2, hspace=0.5, wspace=0.22, left=0.06, right=0.95, top=0.79, bottom=0.07)
    obs = info["observer"]
    start = _t(info["window_start_utc"])
    fig.text(0.06, 0.965, f"{info['satellite']} over {obs['name']}: its real passes over {info['window_days']:g} days",
             fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.925, f"Orbit: CelesTrak TLE, epoch {info['tle_epoch_utc'][:16]} UTC ({info['tle_age_at_start_days']:.2f} days "
             f"before the window), computed with SGP4 (Skyfield {info['versions']['skyfield']}).  Observer {obs['lat']:.4f}° N, "
             f"{-obs['lon']:.4f}° W.  From {start:%d %b %Y %H:%M} UTC.\n"
             f"{info['passes']} passes above the horizon, {info['visible_passes']} visible: some of the pass is in sunlight while the sky is "
             f"dark (Sun more than {-info['dark_sun_alt_deg']:g}° below the horizon).  Ideal conditions: no atmosphere.",
             fontsize=9.8, color=INK2, va="top")
    key = [(VIS, "visible: sunlit, sky dark"), (LIT, "sunlit, sky too bright"), (SHADOW, "in Earth's shadow")]

    # (a) sky chart
    ax = fig.add_subplot(gs[0, 0], projection="polar")
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    for n in np.unique(s["pass"]):
        m = s["pass"] == n
        ax.scatter(np.radians(s["azimuth_deg"][m]), 90 - s["elev_deg"][m], c=_state(s, m), s=4, lw=0)
    ax.set_ylim(0, 90); ax.set_yticks([0, 30, 60, 90]); ax.set_yticklabels(["90°", "60°", "30°", "0°"], color=INK2, fontsize=9)
    ax.set_xticks(np.radians([0, 90, 180, 270])); ax.set_xticklabels(["N", "E", "S", "W"])
    ax.grid(color=GRID); ax.set_facecolor(SURF)
    for c, lab in key:
        ax.plot([], [], "o", color=c, label=lab)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, fontsize=9.5)
    _title(ax, "Every pass on the sky", "centre = straight overhead, edge = horizon (map view: north up, east right)", pad=40)

    # (b) when and how high
    ax = fig.add_subplot(gs[0, 1]); _grid(ax)
    for p in passes:
        t = _t(p["highest_utc"]); e = float(p["max_elev_deg"])
        col = VIS if p["visible"] == "1" else (LIT if float(p["frac_sunlit"]) > 0 else SHADOW)
        ax.vlines(t, 0, e, color=col, lw=3)
        ax.plot(t, e, "o", color=col, ms=6, mec=SURF)
    ax.set_ylim(0, 92); ax.set_ylabel("highest elevation of the pass (degrees)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    _title(ax, "When the passes happen, and how high they get", "UTC; colour as in the sky chart (by the pass as a whole)")

    # (c) the best visible pass over time
    vis = [p for p in passes if p["visible"] == "1"] or passes
    best = max(vis, key=lambda p: float(p["max_elev_deg"]))
    n = int(best["pass"]); m = s["pass"] == n
    ax = fig.add_subplot(gs[1, 0]); _grid(ax)
    tt = s["seconds_from_rise"][m] / 60
    shade = s["sunlit"][m] == 0
    for k in np.nonzero(shade)[0]:
        ax.axvspan(tt[k] - 2.5 / 60, tt[k] + 2.5 / 60, color="#ecebe6", lw=0)
    ax.scatter(tt, s["elev_deg"][m], c=_state(s, m), s=10, lw=0, zorder=3)
    ax.set_xlabel(f"minutes after rise ({best['rise_utc'][:16].replace('T', ' ')} UTC)"); ax.set_ylabel("elevation (degrees)")
    ax.set_ylim(0, 92)
    ax2 = ax.twinx(); ax2.plot(tt, s["range_km"][m], color=INK, lw=1.6, ls=(0, (4, 2)))
    ax2.set_ylabel("distance (km), dashed", color=INK2); ax2.spines["right"].set_visible(True); ax2.tick_params(length=0)
    ax2.set_ylim(0, s["range_km"][m].max() * 1.1)
    entry = best["enters_shadow_utc"]
    sub = f"pass {n}: highest {float(best['max_elev_deg']):.0f}°, closest {float(best['min_range_km']):.0f} km"
    if entry:
        sub += f"; enters Earth's shadow at {entry[11:19]} UTC (grey band)"
    _title(ax, "The highest visible pass, moment by moment", sub)

    # (d) zenith angle against distance, with the formula
    ax = fig.add_subplot(gs[1, 1]); _grid(ax)
    zen = 90 - s["elev_deg"]
    h = float(np.median(s["height_km"]))
    z = np.linspace(0, 90, 200); e = np.radians(90 - z)
    ax.plot(z, np.sqrt((R_EARTH + h) ** 2 - (R_EARTH * np.cos(e)) ** 2) - R_EARTH * np.sin(e), color="#d9d8d2", lw=9,
            solid_capstyle="round", zorder=1, label=f"formula, height {h:.0f} km (METHODS §4b)")
    sc = ax.scatter(zen, s["range_km"], c=s["phase_deg"], cmap="viridis", s=9, lw=0, vmin=0, vmax=180, zorder=3)
    cb = fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.045); cb.set_label("phase angle (degrees)", color=INK2); cb.outline.set_visible(False)
    ax.set_xlim(0, 90); ax.set_xlabel("zenith angle (degrees from straight overhead)"); ax.set_ylabel("distance (km)")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    _title(ax, "Zenith angle against distance, every sample", "closest overhead, about 3 times further at the horizon; colour = Sun angle")

    out = os.path.join(folder, "passes_overview.png")
    _write(out, lambda p: fig.savefig(p, dpi=120, facecolor=SURF)); plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    folders = sys.argv[1:] or [os.path.dirname(p) for p in glob.glob(os.path.join(ROOT, "real_passes", "*", "run_info.json"))]
    for f in folders:
        figure(os.path.abspath(f))
