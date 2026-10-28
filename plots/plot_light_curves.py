"""
plot_light_curves.py - the graphs for light_curves.py: does a sequence of measurements beat a single snapshot,
and can a stable satellite be told from a tumbling one?

  python plot_light_curves.py [repo folder]        (default: the folder above this script)

Reads   light_curves/data/spin_*.csv, pass_*.csv     (made by light_curves.py in Blender)
        brightness_map/data/map_A.csv, map_C.csv     (optional: Earth-pointing vs any-orientation panel)
Writes  light_curves/light_curve_degeneracy.png      sequences vs snapshots
        light_curves/stable_vs_tumbling.png          the pass, three ways, and what Earth-pointing rules out
        light_curves/data/summary_stats.json         the numbers quoted
Needs Python with numpy and matplotlib.

Magnitudes are real apparent magnitudes, converted exactly as in plot_brightness_map.py: the spin library and
the brightness map as seen from 1,000 km, the pass from the satellite's real distance at each moment
(1,280-2,160 km).  No atmosphere; fainter than DARK_MAG = dark.

Matching a stretch of light curve: two spin axes "look the same" over k consecutive measurements if, for some
starting point on the other axis's curve (the spin phase at the start is unknown), every one of the k
brightness values agrees within MAG_TOL magnitudes (two dark values always agree).
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
D = os.path.join(ROOT, "light_curves", "data") + os.sep
BMD = os.path.join(ROOT, "brightness_map", "data") + os.sep
OUT = os.path.join(ROOT, "light_curves")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_brightness_map as pbm                    # magnitude conversion and degeneracy measure
DARK_MAG = pbm.DARK_MAG
MAG_TOL = 0.1
ALT_KM, R_EARTH, MIN_ELEV = 705.0, 6371.0, 10.0   # Aqua's orbit; observer must see it at least 10 deg up

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COL = {"A": "#2a78d6", "C": "#eb6834"}
NAME = {"A": "Aqua (detailed)", "C": "Suomi NPP (low-poly)"}
CASE_COL = {"stable": "#1baf7a", "slow_spin": "#eda100", "tumble": "#c0392b"}
CASE_NAME = {"stable": "stable, Earth-pointing", "slow_spin": "slow spin (0.8°/s)", "tumble": "tumbling (6°/s)"}
PHASE_LS = {30: "-", 90: (0, (5, 2)), 150: (0, (1, 1.5))}


def _write(dest, saver):
    """Save via a temp file, then copy over: writing straight onto an existing file can fail on some mounted drives."""
    tmp = os.path.join(tempfile.gettempdir(), "_plot_tmp_" + os.path.basename(dest))
    saver(tmp)
    shutil.copyfile(tmp, dest)
    os.remove(tmp)


def _rows(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def reference():
    """Distance the spin-library magnitudes are quoted at, and a description for the figures."""
    return pbm.REF_RANGE_KM, f"real apparent magnitudes as seen from {pbm.REF_RANGE_KM:,.0f} km"


def to_mag(b, range_km):
    """Real apparent magnitude at range_km (a number or one per value), as in plot_brightness_map.py."""
    return pbm.real_mag(b, range_km)


def load_spins(ref):
    """{key: {phase: (mags[n_axes, n_frames], axes[n_axes, 3])}} for complete phases only."""
    out = {}
    for key in ("A", "C"):
        rows = _rows(D + f"spin_{key}.csv")
        by = {}
        for r in rows:
            by.setdefault(int(r["phase_set_deg"]), {}).setdefault(int(r["axis_i"]), []).append(r)
        for ph, axes in by.items():
            n = max(axes) + 1
            if len(axes) != n:
                continue
            T = len(axes[0])
            M = np.empty((n, T)); A = np.empty((n, 3))
            for i in range(n):
                rr = sorted(axes[i], key=lambda r: int(r["frame"]))
                M[i] = to_mag([float(r["brightness"]) for r in rr], ref)
                A[i] = [float(rr[0][c]) for c in ("axis_x", "axis_y", "axis_z")]
            out.setdefault(key, {})[ph] = (M, A)
    return out


def curve_degeneracy(M):
    """Share of other spin axes matching a stretch of k measurements, for k = 1 ... T (mean over start points)."""
    n, T = M.shape
    res = np.zeros(T)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            Dm = np.abs(M[i][:, None] - M[j][None, :]) <= MAG_TOL + 1e-9        # [start on i, start on j]
            W = Dm.copy()
            for k in range(1, T + 1):
                if k > 1:
                    W &= np.roll(np.roll(Dm, -(k - 1), 0), -(k - 1), 1)
                res[k - 1] += W.any(1).mean()
    return res / (n * (n - 1))


def best_rms(M):
    """Smallest rms magnitude difference between two axes' full curves over every relative start point."""
    n, T = M.shape
    R = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            R[i, j] = min(np.sqrt(np.mean((M[i] - np.roll(M[j], s)) ** 2)) for s in range(T))
    return R


def load_passes(ref):
    out = {}
    for key in ("A", "C"):
        for r in _rows(D + f"pass_{key}.csv"):
            out.setdefault(key, {}).setdefault(r["case"], []).append(r)
    for key in out:
        for case, rr in out[key].items():
            rr.sort(key=lambda r: int(r["frame"]))
            out[key][case] = dict(t=np.array([float(r["t_s"]) for r in rr]),
                                  mag=to_mag([float(r["brightness"]) for r in rr], [float(r["range_km"]) for r in rr]),
                                  phase=np.array([float(r["phase_deg"]) for r in rr]))
    return out


def load_map(ref):
    """Brightness-map geometries: phase, magnitude, and whether an Earth-pointing satellite could be seen that way."""
    cos_lim = math.cos(math.asin(R_EARTH / (R_EARTH + ALT_KM) * math.cos(math.radians(MIN_ELEV))))
    out = {}
    for key in ("A", "C"):
        rows = _rows(BMD + f"map_{key}.csv")
        if not rows:
            continue
        a = dict(phase_deg=np.array([float(r["phase_deg"]) for r in rows]),
                 mag=to_mag([float(r["brightness"]) for r in rows], ref),
                 obs_z=np.array([float(r["obs_z"]) for r in rows]))
        a["dark"] = a["mag"] >= DARK_MAG - 1e-9
        a["earth"] = a["obs_z"] <= -cos_lim          # observer below the satellite, within the visible cone
        out[key] = a
    return out, math.degrees(math.acos(cos_lim))


def _style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.facecolor": SURF,
                         "figure.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})


def _grid(ax):
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)


def _title(ax, head, sub):
    ax.set_title(head, loc="left", fontsize=13, fontweight="bold", color=INK, pad=26)
    ax.text(0, 1.025, sub, transform=ax.transAxes, fontsize=9.8, color=INK2, va="bottom")


def _heading(fig, head, sub):
    fig.text(0.06, 0.965, head, fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.915, sub, fontsize=9.8, color=INK2, va="top")


def degeneracy_figure(spins, refname, st):
    if not spins:
        print("no spin-library data yet: skipping light_curve_degeneracy.png")
        return
    _style()
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.62, wspace=0.22, left=0.06, right=0.975, top=0.80, bottom=0.07)
    any_key = next(iter(spins)); any_ph = next(iter(spins[any_key]))
    n, T = spins[any_key][any_ph][0].shape
    step = 360 // T
    _heading(fig, "One snapshot vs a sequence: how many different spins look the same?",
             f"Each satellite spins about {n} different axes (spread over the sphere), Sun and observer fixed, a measurement every {step}° of spin.  "
             f"Ideal conditions; {refname}.\nTwo axes 'look the same' if some stretch of one curve matches the other within ±{MAG_TOL} mag "
             "at every measurement (the starting spin phase is unknown).")

    # (a) example curves
    ax = fig.add_subplot(gs[0, 0]); _grid(ax)
    key = "A" if "A" in spins else any_key
    ph = 90 if 90 in spins[key] else next(iter(spins[key]))
    M, A = spins[key][ph]
    x = np.arange(T) * step
    for c, i in zip(("#2a78d6", "#eb6834", "#1baf7a", "#8e44ad"), np.linspace(0, n - 1, 4).astype(int)):
        ax.plot(x, M[i], color=c, lw=2, marker="o", ms=3, label=f"axis ({A[i][0]:+.2f}, {A[i][1]:+.2f}, {A[i][2]:+.2f})")
    ax.set_xlim(0, 360 - step); ax.set_xticks(range(0, 361, 60)); ax.set_xlabel("spin angle (degrees)")
    ax.set_ylim(DARK_MAG + 0.5, max(-0.3, np.floor(M.min()) - 0.3)); ax.set_ylabel(f"apparent magnitude at {pbm.REF_RANGE_KM:,.0f} km (up = brighter)")
    ax.legend(loc="lower left", frameon=False, fontsize=9, ncol=2)
    _title(ax, f"{NAME[key]}: four of the {n} spin axes", f"phase angle {ph}°; each spin axis gives its own light curve")

    # (b) degeneracy vs sequence length
    ax = fig.add_subplot(gs[0, 1]); _grid(ax)
    for k in spins:
        for ph, (M, _) in sorted(spins[k].items()):
            d = curve_degeneracy(M) * 100
            st.setdefault("spin_degeneracy_pct", {}).setdefault(k, {})[str(ph)] = {
                f"k{kk}": round(float(d[kk - 1]), 2) for kk in (1, 2, 3, 6, 12, 18, T) if kk <= T}
            ax.plot(np.arange(1, T + 1), d, color=COL[k], lw=2, ls=PHASE_LS.get(ph, "-"), label=f"{NAME[k]}, phase {ph}°")
    ax.set_xlim(1, T); ax.set_ylim(0, None); ax.set_xlabel(f"number of measurements in a row ({step}° of spin apart)")
    ax.set_ylabel("other spin axes that match (%)")
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    _title(ax, "The longer the sequence, the fewer spins fit", "1 measurement = a snapshot; the curve shows how fast the look-alikes are ruled out")

    # (c, d) which axes are confusable
    for slot, k in enumerate([k for k in ("A", "C") if k in spins][:2]):
        ph = 90 if 90 in spins[k] else next(iter(spins[k]))
        R = best_rms(spins[k][ph][0])
        np.fill_diagonal(R, np.nan)
        ax = fig.add_subplot(gs[1, slot])
        im = ax.imshow(R, cmap="viridis", vmin=0, vmax=np.nanpercentile(R, 95), interpolation="nearest", aspect="auto")
        cb = fig.colorbar(im, ax=ax, pad=0.01, fraction=0.045); cb.set_label("closest rms difference (mag)", color=INK2); cb.outline.set_visible(False)
        ax.set_xlabel("spin axis"); ax.set_ylabel("spin axis"); ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        close = int(np.sum(np.triu(R < MAG_TOL, 1)))
        st.setdefault("full_curve_lookalike_pairs", {})[k] = {"phase": ph, "pairs_within_tol": close, "pairs": n * (n - 1) // 2,
                                                              "median_best_rms_mag": round(float(np.nanmedian(R)), 3)}
        _title(ax, f"{NAME[k]}: how alike are two whole spins?",
               f"phase {ph}°; dark = nearly identical light curves.  {close} of {n * (n - 1) // 2} pairs within {MAG_TOL} mag rms")
    out = os.path.join(OUT, "light_curve_degeneracy.png")
    _write(out, lambda p: fig.savefig(p, dpi=130, facecolor=SURF)); plt.close(fig)
    print("saved", out)


def tumbling_figure(passes, bmap, cone_deg, refname, st):
    if not passes:
        print("no pass data yet: skipping stable_vs_tumbling.png")
        return
    _style()
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.62, wspace=0.22, left=0.06, right=0.975, top=0.80, bottom=0.07)
    _heading(fig, "Stable or tumbling? The same pass seen three ways",
             f"Dawn-dusk pass (705 km, about 8 minutes, mostly backlit).  Stable = Earth-pointing, as these satellites really fly; "
             f"the others turn while the pass goes on.\nIdeal conditions (no atmosphere); real apparent magnitudes at the satellite's "
             f"actual distance (1,280–2,160 km); bottom-left panel at {pbm.REF_RANGE_KM:,.0f} km.")
    keys = [k for k in ("A", "C") if k in passes]
    for slot, k in enumerate(keys[:2]):
        ax = fig.add_subplot(gs[0, slot]); _grid(ax)
        for case in ("stable", "slow_spin", "tumble"):
            if case in passes[k]:
                p = passes[k][case]
                ax.plot(p["t"], p["mag"], color=CASE_COL[case], lw=2, label=CASE_NAME[case])
        ax.set_xlabel("time into the pass (s)"); ax.set_ylabel("apparent magnitude (up = brighter)")
        lo = min(passes[k][c]["mag"].min() for c in passes[k])
        ax.set_ylim(DARK_MAG + 1.8, max(-0.3, np.floor(lo) - 0.3))          # room under the dark floor for the key
        ax.axhline(DARK_MAG, color=INK2, lw=0.9, ls=(0, (4, 3)))
        ax.axhline(pbm.NAKED_EYE, color="#b9b8b0", lw=1.1)
        ax.text(p["t"][-1], pbm.NAKED_EYE - 0.15, "naked-eye limit", ha="right", va="bottom", fontsize=9, color=INK2)
        ax.legend(loc="lower center", frameon=False, fontsize=9.5, ncol=3)
        _title(ax, f"{NAME[k]}: light curve over the pass",
               "smooth = stable; fast regular flicker = turning; a lone one-frame spike = a glint off a shiny part")

    # (c) what Earth-pointing rules out
    ax = fig.add_subplot(gs[1, 0]); _grid(ax)
    if bmap:
        k = "A" if "A" in bmap else next(iter(bmap))
        a = bmap[k]
        ax.scatter(a["phase_deg"][~a["earth"]], a["mag"][~a["earth"]], s=5, color="#c9c8c2", lw=0, label="any orientation (tumbling)")
        ax.scatter(a["phase_deg"][a["earth"]], a["mag"][a["earth"]], s=9, color=COL[k], lw=0, label="possible for an Earth-pointing satellite")
        ax.set_xlim(0, 180); ax.set_xticks(range(0, 181, 30)); ax.set_xlabel("phase angle (degrees)")
        ax.set_ylim(DARK_MAG + 0.5, 0.7); ax.set_ylabel(f"apparent magnitude at {pbm.REF_RANGE_KM:,.0f} km (up = brighter)")
        ax.legend(loc="lower left", frameon=False, fontsize=9.5)
        for kk in bmap:
            b = bmap[kk]
            sub = {q: b[q][b["earth"]] for q in ("phase_deg", "mag", "dark")}
            st.setdefault("earth_pointing_vs_any", {})[kk] = {
                "geometries_any": int(len(b["mag"])), "geometries_earth_pointing": int(b["earth"].sum()),
                "median_degeneracy_any": round(float(np.median(pbm.degeneracy(b))), 3),
                "median_degeneracy_earth_pointing": round(float(np.median(pbm.degeneracy(sub))), 3),
                "range_p5_p95_any_mag": round(float(np.ptp(np.percentile(b["mag"][~b["dark"]], [5, 95]))), 2),
                "range_p5_p95_earth_mag": round(float(np.ptp(np.percentile(sub["mag"][~sub["dark"]], [5, 95]))), 2)}
        e = st["earth_pointing_vs_any"][k]
        _title(ax, f"{NAME[k]}: what being Earth-pointing rules out",
               f"from the brightness map; observer within {cone_deg:.0f}° of straight down.  {e['geometries_earth_pointing']} of {e['geometries_any']} geometries remain")
    else:
        ax.axis("off"); ax.text(0, 0.5, "brightness-map data not found", color=INK2)

    # (d) flicker: typical change between measurements
    ax = fig.add_subplot(gs[1, 1]); _grid(ax)
    cases = ["stable", "slow_spin", "tumble"]
    w = 0.38
    for n_, k in enumerate(keys):
        vals = []
        for case in cases:
            p = passes[k].get(case)
            if p is None:
                vals.append(np.nan); continue
            dt = np.median(np.diff(p["t"]))
            # median, not mean: a stable satellite still gives the odd one-frame glint, which would swamp a mean
            v = float(np.median(np.abs(np.diff(p["mag"]))) / dt * 10)          # magnitudes per 10 s
            st.setdefault("pass_mag_min_median_max", {}).setdefault(k, {})[case] = [
                round(float(x), 2) for x in (p["mag"].min(), np.median(p["mag"]), p["mag"].max())]
            vals.append(v)
            st.setdefault("flicker_mag_per_10s", {}).setdefault(k, {})[case] = round(v, 3)
        xs = np.arange(len(cases)) + (n_ - (len(keys) - 1) / 2) * w
        ax.bar(xs, vals, width=w * 0.92, color=COL[k], label=NAME[k])
        for xx, v in zip(xs, vals):
            if not np.isnan(v):
                ax.text(xx, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks(range(len(cases))); ax.set_xticklabels([CASE_NAME[c] for c in cases])
    ax.set_ylabel("typical brightness change (mag per 10 s)")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    _title(ax, "Flicker tells them apart", "typical (median) change between neighbouring measurements, scaled to 10 s")
    out = os.path.join(OUT, "stable_vs_tumbling.png")
    _write(out, lambda p: fig.savefig(p, dpi=130, facecolor=SURF)); plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    os.makedirs(D, exist_ok=True)
    ref, refname = reference()
    st = {"reference": refname, "mag_tol": MAG_TOL}
    degeneracy_figure(load_spins(ref), refname, st)
    bmap, cone = load_map(ref)
    tumbling_figure(load_passes(ref), bmap, cone, refname, st)
    json.dump(st, open(D + "summary_stats.json", "w"), indent=1)
    print(json.dumps(st, indent=1))
