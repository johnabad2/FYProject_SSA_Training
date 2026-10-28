"""
make_videos.py - lay out the frames of the two explainer videos (pictures + measured brightness curve).

  python script_code/make_videos.py            (run from the project folder, outside Blender)

Reads   videos/frames/stable_vs_tumbling/*.png, videos/frames/telescope_view/*.png   (video_frames.py)
        light_curves/data/pass_A.csv, spin_A.csv                                      (light_curves.py)
Writes  videos/composed/<name>/f0001.png ...   then encode them in Blender: video_frames.py encode(<name>)
Needs Python with numpy, matplotlib and Pillow.

The brightness curves are the measured data (linear, no fill light), in magnitudes on the same scale as the
other light-curve graphs.  The pictures have a faint fill light so the shape stays visible.
In telescope_view the middle panels add the picture's light up in bigger and bigger blocks: the further away,
the coarser, until the whole satellite is one pixel (the brightness of that pixel is the light curve).
"""
import csv
import os
import shutil
import sys

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "plots"))
sys.argv = sys.argv[:1]                        # plot_light_curves reads the repo folder from argv
import plot_light_curves as plc                # same magnitude scale as the light-curve graphs

FR = os.path.join(ROOT, "videos", "frames")
CO = os.path.join(ROOT, "videos", "composed")
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BG = (252, 252, 251)
BRIGHTEN = 2.5            # stable_vs_tumbling pictures only: the pass is mostly backlit and very dark
FD = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
F = lambda s: ImageFont.truetype(os.path.join(FD, "DejaVuSans.ttf"), s)
FB = lambda s: ImageFont.truetype(os.path.join(FD, "DejaVuSans-Bold.ttf"), s)


def _fresh(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)


def _graph(x, curves, k, xlabel, w=1920, h=400, dpi=100, xlim=None, title=""):
    """curves: [(label, colour, values)]; draw faint full curves, solid up to index k, and a dot at k."""
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor=SURF)
    ax = fig.add_axes([0.06, 0.2, 0.92, 0.62]); ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
    lo = min(v.min() for _, _, v in curves)
    for lab, c, v in curves:
        ax.plot(x, v, color=c, lw=1, alpha=0.2)
        ax.plot(x[:k + 1], v[:k + 1], color=c, lw=2.4, label=lab)
        ax.plot(x[k], v[k], "o", ms=8, color=c, mec=SURF, mew=1.2)
    ax.axvline(x[k], color="#b9b8b0", lw=1)
    ax.axhline(plc.DARK_MAG, color=INK2, lw=0.8, ls=(0, (4, 3)))
    ax.set_ylim(plc.DARK_MAG + 0.6, max(-0.3, np.floor(lo) - 0.3))
    ax.set_xlim(*(xlim or (x[0], x[-1])))
    ax.set_xlabel(xlabel, color=INK2); ax.set_ylabel("apparent magnitude (up = brighter)", color=INK2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    if len(curves) > 1:
        ax.legend(loc="upper left", frameon=False, ncol=len(curves), fontsize=11)
    fig.text(0.06, 0.9, title, fontsize=14, fontweight="bold", color=INK)
    fig.canvas.draw()
    im = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
    plt.close(fig)
    return im


def stable_vs_tumbling():
    ref, _ = plc.reference()
    p = plc.load_passes(ref)["A"]
    cases = ["stable", "slow_spin", "tumble"]
    n = len(p["stable"]["t"])
    t = p["stable"]["t"]
    out = os.path.join(CO, "stable_vs_tumbling"); _fresh(out)
    for k in range(n):
        c = Image.new("RGB", (1920, 70 + 640 + 400), BG)
        d = ImageDraw.Draw(c)
        d.text((16, 10), "Aqua over one pass, three ways: stable (Earth-pointing), slowly spinning, tumbling",
               font=FB(24), fill=(11, 11, 11))
        d.text((16, 42), f"Seen from the ground observer.  Time {t[k]:4.0f} s of {t[-1]:.0f} s   |   "
                         f"Sun–satellite–observer angle {p['stable']['phase'][k]:3.0f}°   |   pictures brightened, with a faint fill light, "
                         "so the shape is visible (the curve is measured without either)",
               font=F(15), fill=(82, 81, 78))
        for j, case in enumerate(cases):
            im = Image.open(os.path.join(FR, "stable_vs_tumbling", f"{case}_{k + 1:04d}.png")).convert("RGB")
            im = ImageEnhance.Brightness(im).enhance(BRIGHTEN)          # mostly backlit pass: lift for viewing
            c.paste(im.resize((640, 640), Image.LANCZOS), (j * 640, 70))
            d.rectangle([j * 640 + 8, 78, j * 640 + 22, 92], fill=plc.CASE_COL[case])
            d.text((j * 640 + 30, 75), plc.CASE_NAME[case], font=FB(17), fill=(255, 255, 255))
        g = _graph(t, [(plc.CASE_NAME[cs], plc.CASE_COL[cs], p[cs]["mag"]) for cs in cases], k,
                   "time into the pass (s)", title="Measured brightness (the light curve a telescope records)")
        c.paste(g, (0, 710))
        c.save(os.path.join(out, f"f{k + 1:04d}.png"))
    print("composed", n, "frames ->", out)


def telescope_view(loops=2):
    ref, _ = plc.reference()
    axis_i = int(open(os.path.join(FR, "telescope_view", "axis.txt")).read())
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "light_curves", "data", "spin_A.csv")))
            if int(r["phase_set_deg"]) == 90 and int(r["axis_i"]) == axis_i]
    rows.sort(key=lambda r: int(r["frame"]))
    spin = np.array([float(r["spin_deg"]) for r in rows])
    mag = plc.to_mag([float(r["brightness"]) for r in rows], ref)
    ax_vec = [float(rows[0][c]) for c in ("axis_x", "axis_y", "axis_z")]
    pics = [np.asarray(Image.open(os.path.join(FR, "telescope_view", f"spin_{int(s):03d}.png")).convert("RGB")) for s in spin]
    lum = []
    for p_ in pics:
        L = (p_ / 255.0) ** 2.2 @ np.array([0.2126, 0.7152, 0.0722])                       # back to linear light
        bg = np.median(np.concatenate([L[0], L[-1], L[:, 0], L[:, -1]]))                     # the fill-lit sky
        lum.append(np.clip(L - bg, 0, None))                                                 # count only the satellite
    blocks = [16, 80, 640]

    def binned(L, b):
        m = L.shape[0] // b
        return L[:m * b, :m * b].reshape(m, b, m, b).sum(axis=(1, 3))
    top = {b: max(binned(L, b).max() for L in lum) for b in blocks}       # same scale through the whole video
    out = os.path.join(CO, "telescope_view"); _fresh(out)
    n = len(spin); idx = 0
    for loop in range(loops):
        for k in range(n):
            idx += 1
            c = Image.new("RGB", (1920, 70 + 680 + 380), BG)
            d = ImageDraw.Draw(c)
            d.text((16, 10), "What a telescope actually sees: the shape washes out to a single point of light",
                   font=FB(24), fill=(11, 11, 11))
            d.text((16, 42), f"Aqua spinning about axis ({ax_vec[0]:+.2f}, {ax_vec[1]:+.2f}, {ax_vec[2]:+.2f}); Sun 90° from the observer.   "
                             f"Spin {spin[k]:3.0f}°", font=F(15), fill=(82, 81, 78))
            c.paste(Image.fromarray(pics[k]).resize((640, 640), Image.LANCZOS), (0, 100))
            d.text((10, 74), "close up (faint fill light added)", font=FB(16), fill=(11, 11, 11))
            for j, b in enumerate(blocks):
                v = np.sqrt(np.clip(binned(lum[k], b) / top[b], 0, 1))        # square root: easier to see faint parts
                im = Image.fromarray((v * 255).astype(np.uint8)).resize((400, 400), Image.NEAREST).convert("RGB")
                x0 = 690 + j * 410
                c.paste(im, (x0, 220))
                lab = {16: "further away", 80: "much further", 640: "orbital range: one pixel"}[b]
                d.text((x0, 190), lab, font=FB(16), fill=(11, 11, 11))
            d.text((690, 634), "Each panel adds the light up in bigger blocks.  Only the last one is what a ground telescope gets:",
                   font=F(15), fill=(82, 81, 78))
            d.text((690, 656), "one number per moment, its brightness.  That number over time is the light curve below.",
                   font=F(15), fill=(82, 81, 78))
            g = _graph(spin, [("brightness", "#2a78d6", mag)], k, "spin angle (degrees)", h=380,
                       xlim=(0, 360 - (spin[1] - spin[0])), title="Measured brightness of that single pixel")
            c.paste(g, (0, 750))
            c.save(os.path.join(out, f"f{idx:04d}.png"))
    print("composed", idx, "frames ->", out)


if __name__ == "__main__":
    stable_vs_tumbling()
    telescope_view()
