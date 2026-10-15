"""
plot_material_tests.py - the graphs for the material tests (flat plate / matte sphere / shiny panel).

  python plot_material_tests.py [repo folder]        (default: the folder above this script)

Reads   material_tests/data/*.csv            (made by material_tests.py inside Blender)
        material_tests/samples/*.png
Writes  material_tests/brightness_vs_angle.png   the main figure
        material_tests/sample_renders.png        pictures of each object at six spin angles
        material_tests/data/summary_stats.json   the numbers quoted in the meeting
Needs Python with numpy, matplotlib and Pillow.  Run it outside Blender (any Python).
"""
import csv
import json
import os
import shutil
import sys
import tempfile
import textwrap

import matplotlib
import numpy as np
from matplotlib.ticker import FuncFormatter, LogLocator
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FONTS = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")


def _write(dest, saver):
    """Save via a temp file, then copy over: writing straight onto an existing file can fail on some mounted drives."""
    tmp = os.path.join(tempfile.gettempdir(), "_plot_tmp_" + os.path.basename(dest))
    saver(tmp)
    shutil.copyfile(tmp, dest)
    os.remove(tmp)



def stats():
    """Numbers that back up the graphs (written to summary_stats.json)."""
    D = os.path.join(ROOT, "material_tests", "data") + os.sep
    def load(n):
        a = np.genfromtxt(D + n, delimiter=",", names=True, dtype=None, encoding="utf-8")
        return a
    plate, sph, shiny, dist = (load(n) for n in ("spin_plate_diffuse.csv", "spin_sphere_diffuse.csv",
                                                 "spin_panel_shiny.csv", "distance_sphere_diffuse.csv"))
    ref = sph["brightness"].mean()
    out = {"reference_matte_sphere_flux": float(ref), "sphere_spread_pct": float(100 * (sph["brightness"].max() - sph["brightness"].min()) / ref)}

    # plate: Lambert theory  flux ~ k * [cos(i)+ * cos(e)+] for front and back faces
    th = np.radians(plate["spin_deg"]); c1 = np.cos(th - np.radians(60)); c2 = np.cos(th)
    model = np.maximum(c1, 0) * np.maximum(c2, 0) + np.maximum(-c1, 0) * np.maximum(-c2, 0)
    k = (model * plate["brightness"]).sum() / (model * model).sum()
    rel = plate["brightness"] / ref
    out["plate"] = {"peak_rel": float(rel.max()), "peak_at_deg": float(plate["spin_deg"][rel.argmax()]),
                    "theory_rms_err_pct_of_peak": float(100 * np.sqrt(np.mean((plate["brightness"] - k * model) ** 2)) / plate["brightness"].max()),
                    "frac_of_spin_above_50pct_of_peak": float(np.mean(plate["brightness"] > 0.5 * plate["brightness"].max())),
                    "frac_of_spin_dark_below_1pct": float(np.mean(plate["brightness"] < 0.01 * plate["brightness"].max())),
                    "area_vs_cos_max_dev_pct": float(100 * np.max(np.abs(plate["apparent_area_px"] / plate["apparent_area_px"].max() - np.abs(np.cos(th)))))}

    # shiny
    a = shiny["spin_deg"]; f = shiny["brightness"]
    peak = f.max(); out["shiny"] = {"peak_rel": float(peak / ref), "peak_at_deg": float(a[f.argmax()])}
    floor = np.median(f); out["shiny"]["floor_rel"] = float(floor / ref)
    out["shiny"]["peak_over_floor"] = float(peak / floor)
    for centre in (30, 210):
        m = np.abs(a - centre) <= 3; aa, ff = a[m], f[m]
        half = ff.max() / 2; above = aa[ff >= half]
        out["shiny"][f"flash_{centre}"] = {"peak_rel": float(ff.max() / ref), "peak_at": float(aa[ff.argmax()]),
                                           "fwhm_deg": float(above.max() - above.min()), "n_points_in_fwhm": int(len(above))}
    # fraction of the 360 deg during which it is brighter than the matte sphere (reference)
    # (coarse 2 deg grid only, so the fine sampling does not bias the fraction)
    coarse = np.isclose(a % 2, 0) | np.isclose(a % 2, 2)
    out["shiny"]["coarse_frac_brighter_than_sphere"] = float(np.mean(f[coarse] > ref))
    out["shiny"]["fraction_of_spin_above_1pct_of_peak_estimate_deg"] = float(
        sum(np.diff(np.sort(a[f > 0.01 * peak]))[np.diff(np.sort(a[f > 0.01 * peak])) < 1.0]))

    # distance
    d = dist["distance_m"].astype(float)
    sl_b = np.polyfit(np.log(d), np.log(dist["brightness"]), 1)[0]
    sl_a = np.polyfit(np.log(d), np.log(dist["apparent_area_px"]), 1)[0]
    out["distance"] = {"brightness_slope": float(sl_b), "area_slope": float(sl_a),
                       "brightness_over_area_spread_pct": float(100 * np.ptp(dist["brightness"] / dist["apparent_area_px"]) / np.mean(dist["brightness"] / dist["apparent_area_px"]))}
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(D, "summary_stats.json"), "w"), indent=1)
    return out


def main_figure():
    """The 2 x 3 figure: plate, sphere, shiny panel, glint zoom, distance, summary text."""
    D = os.path.join(ROOT, "material_tests", "data") + os.sep
    def load(n): return np.genfromtxt(D + n, delimiter=",", names=True, dtype=None, encoding="utf-8")
    plate, sph, shiny, dist = (load(n) for n in ("spin_plate_diffuse.csv", "spin_sphere_diffuse.csv",
                                                 "spin_panel_shiny.csv", "distance_sphere_diffuse.csv"))
    ref = sph["brightness"].mean()

    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
    C_PLATE, C_SPH, C_SHINY = "#2a78d6", "#eb6834", "#1baf7a"     # categorical slots 1-3, fixed per object
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "text.color": INK, "axes.facecolor": SURF, "figure.facecolor": SURF,
                         "axes.spines.top": False, "axes.spines.right": False})

    def style(ax):
        ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
        for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
        ax.tick_params(length=0)

    def spin_axis(ax):
        ax.set_xlim(0, 360); ax.set_xticks(range(0, 361, 60))
        ax.set_xlabel("spin angle (degrees)")

    def title(ax, head, sub):
        ax.set_title(head, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=24)
        ax.text(0, 1.04, sub, transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")

    fig = plt.figure(figsize=(16, 9.2))
    gs = fig.add_gridspec(2, 3, hspace=0.62, wspace=0.28, left=0.055, right=0.985, top=0.84, bottom=0.085)
    fig.text(0.055, 0.965, "How brightness changes with angle for three kinds of surface", fontsize=17, fontweight="bold", color=INK)
    fig.text(0.055, 0.928, "Brightness = total light the camera receives, relative to the matte sphere (= 1).  Sun and camera are 60° apart; "
             "each object spins about its vertical axis while the Sun and camera stay fixed.", fontsize=10.5, color=INK2)

    # (a) flat plate
    ax = fig.add_subplot(gs[0, 0]); style(ax)
    th = np.radians(plate["spin_deg"]); c1, c2 = np.cos(th - np.radians(60)), np.cos(th)
    model = np.maximum(c1, 0) * np.maximum(c2, 0) + np.maximum(-c1, 0) * np.maximum(-c2, 0)
    k = (model * plate["brightness"]).sum() / (model * model).sum()
    ax.plot(plate["spin_deg"], model * k / ref, color=INK2, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.plot(plate["spin_deg"], plate["brightness"] / ref, color=C_PLATE, lw=2, zorder=3)
    ax.set_ylim(0, 2.2); spin_axis(ax); ax.set_ylabel("relative brightness")
    title(ax, "Flat plate (matte)", "bright only when the face can see both the Sun and the camera")
    ax.text(60, 1.98, "front face", ha="center", fontsize=10, color=INK2)
    ax.text(240, 1.98, "back face", ha="center", fontsize=10, color=INK2)
    ax.annotate("dark: edge-on\nor facing away", xy=(120, 0.02), xytext=(150, 0.55), fontsize=10, color=INK2,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.text(358, 1.55, "Lambert theory\n(cos × cos) lies\nexactly under it", ha="right", fontsize=9.5, color=INK2)

    # (b) matte sphere
    ax = fig.add_subplot(gs[0, 1]); style(ax)
    ax.plot(sph["spin_deg"], sph["brightness"] / ref, color=C_SPH, lw=2)
    ax.set_ylim(0, 2.2); spin_axis(ax)
    title(ax, "Matte sphere", "looks the same from any angle")
    ax.text(180, 1.35, "constant to within 0.05%", ha="center", fontsize=10.5, color=INK2)

    # (c) shiny panel, log
    ax = fig.add_subplot(gs[0, 2]); style(ax)
    ax.plot(shiny["spin_deg"], shiny["brightness"] / ref, color=C_SHINY, lw=1.6)
    ax.set_yscale("log"); ax.set_ylim(1e-4, 5e3); spin_axis(ax)
    ax.yaxis.set_major_locator(LogLocator(base=10, numticks=10))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    title(ax, "Shiny panel (mirror-like)", "dark nearly everywhere, then sudden glints (log scale)")
    ax.axhline(1, color=INK2, lw=0.9, ls=(0, (4, 3)))
    ax.text(358, 1.5, "matte sphere = 1", ha="right", fontsize=9.5, color=INK2)
    ax.annotate("glint at 30°\n≈1200× the sphere", xy=(30, 1200), xytext=(78, 400), fontsize=10, color=INK2,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("second glint at 210°\n(back face)", xy=(210, 1200), xytext=(236, 20), fontsize=10, color=INK2,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))

    # (d) glint zoom
    ax = fig.add_subplot(gs[1, 0]); style(ax)
    m = np.abs(shiny["spin_deg"] - 30) <= 6
    a, f = shiny["spin_deg"][m], shiny["brightness"][m] / ref
    o = np.argsort(a); a, f = a[o], f[o]
    ax.plot(a, f, color=C_SHINY, lw=2, marker="o", ms=3.2, mec=SURF, mew=0.6)
    half = f.max() / 2; above = a[f >= half]
    ax.hlines(half, above.min(), above.max(), color=INK2, lw=1.2)
    ax.text(above.max() + 0.5, half, f"width at half height\n≈ {above.max() - above.min():.1f}°", va="center", fontsize=10, color=INK2)
    ax.set_xlim(24, 36); ax.set_ylim(0, 1400); ax.set_xlabel("spin angle (degrees)"); ax.set_ylabel("relative brightness")
    title(ax, "Zoom on the glint at 30°", "it lasts about a degree and a half of spin")

    # (e) distance
    ax = fig.add_subplot(gs[1, 1]); style(ax)
    d = dist["distance_m"].astype(float); b = dist["brightness"] / ref
    ax.plot(d, b, color=C_SPH, lw=0, marker="o", ms=7, mec=SURF, mew=1.5, zorder=3)
    xs = np.linspace(d.min() * 0.9, d.max() * 1.1, 50)
    ax.plot(xs, b[0] * (d[0] / xs) ** 2, color=INK2, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xticks([10, 20, 40, 80]); ax.set_xticklabels(["10", "20", "40", "80"])
    ax.set_yticks([0.01, 0.03, 0.1, 0.3, 1]); ax.set_yticklabels(["0.01", "0.03", "0.1", "0.3", "1"])
    ax.set_xlim(8, 100); ax.set_ylim(0.005, 1.6)
    ax.set_xlabel("distance from camera (metres)"); ax.set_ylabel("relative brightness")
    title(ax, "Matte sphere moving away", "only its apparent size changes: brightness ∝ 1/distance²")
    ax.text(95, 0.45, "dashed: 1/distance²\nfitted slope −2.01", ha="right", fontsize=10, color=INK2)

    # (f) summary
    ax = fig.add_subplot(gs[1, 2]); ax.axis("off")
    ax.text(0, 1.0, "Reading the charts", fontsize=12.5, fontweight="bold", va="top", color=INK)
    lines = [("Plate", "follows the textbook Lambert curve (within 0.1%). Bright over about 41% of the spin, dark over about 34%."),
             ("Sphere", "the reference: brightness does not depend on spin. Further away it just looks smaller and dimmer."),
             ("Shiny panel", "almost black except at the mirror angle, where it beats the sphere for only about 8% of the spin."),
             ("Why it matters", "a glint is a Sun reflection: it needs Sun, panel and observer to line up, like an Iridium flare.")]
    y = 0.86
    for head, body in lines:
        ax.text(0, y, head, fontsize=10.5, fontweight="bold", va="top", color=INK)
        wrapped = textwrap.fill(body, 38)
        ax.text(0, y - 0.06, wrapped, fontsize=10, va="top", color=INK2, linespacing=1.3)
        y -= 0.07 + 0.052 * (wrapped.count("\n") + 1) + 0.05
    out_png = os.path.join(ROOT, "material_tests", "brightness_vs_angle.png")
    _write(out_png, lambda p: fig.savefig(p, dpi=130, facecolor=SURF))
    plt.close(fig)
    print("saved", out_png)


def sample_sheet():
    """Grid of small renders: 3 objects x 6 spin angles, with the measured brightness under each."""
    D=os.path.join(ROOT,"material_tests")+os.sep
    angs=[0,30,60,90,120,210]
    rows=[("plate_diffuse","Flat plate (matte)"),("sphere_diffuse","Matte sphere"),("panel_shiny","Shiny panel")]
    ref=np.genfromtxt(D+"data/spin_sphere_diffuse.csv",delimiter=",",names=True,dtype=None,encoding="utf-8")["brightness"].mean()   # matte sphere = 1
    def flux(key):
        d={}
        for r in csv.DictReader(open(D+f"data/spin_{key}.csv")): d[round(float(r["spin_deg"]),4)]=float(r["brightness"])
        return d
    F={k:flux(k) for k,_ in rows}
    f=lambda s:ImageFont.truetype(os.path.join(FONTS,"DejaVuSans.ttf"),s)
    fb=lambda s:ImageFont.truetype(os.path.join(FONTS,"DejaVuSans-Bold.ttf"),s)
    S=256;L=190;T=90;W=L+6*S;H=T+3*(S+34)+10
    def lab(v):
        if v<1e-4: return "dark (≈0)"
        if v>=100: return f"{v:,.0f}× sphere"
        if v<0.1: return f"{v:.3f}× sphere"
        return f"{v:.2f}× sphere"
    im=Image.new("RGB",(W,H),(252,252,251));dr=ImageDraw.Draw(im)
    dr.text((20,16),"Sample renders: the same three objects at six spin angles",font=fb(20),fill=(11,11,11))
    dr.text((20,46),"Brightness relative to the matte sphere shown under each picture (Sun and camera 60° apart; background black)",font=f(13),fill=(82,81,78))
    for j,a in enumerate(angs):
        dr.text((L+j*S+S//2-40,T-24),f"spin {a}°",font=fb(14),fill=(11,11,11))
    for i,(k,name) in enumerate(rows):
        y=T+i*(S+34)
        dr.text((20,y+S//2-10),name,font=fb(15),fill=(11,11,11))
        for j,a in enumerate(angs):
            p=Image.open(D+f"samples/{k}_{a:03d}.png").convert("RGBA")
            bg=Image.new("RGBA",p.size,(14,14,16,255));bg.alpha_composite(p)
            im.paste(bg.convert("RGB").resize((S,S)),(L+j*S,y))
            v=F[k][float(a)]/ref
            dr.text((L+j*S+8,y+S+8),lab(v),font=f(13),fill=(11,11,11))
    _write(os.path.join(D,"sample_renders.png"), im.save)
    print("saved", os.path.join(D,"sample_renders.png"))


if __name__ == "__main__":
    stats()
    main_figure()
    sample_sheet()
