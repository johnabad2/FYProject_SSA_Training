"""
make_spin_animation.py - build the spin animation video from the frames made by spin_animation.py.

  python make_spin_animation.py <fidelity_test folder>
Needs Python with Pillow, matplotlib, numpy and ffmpeg.  Writes spin_sun90.mp4 into that folder.

Top: the three satellite versions spinning (same Sun and camera).  Bottom: brightness against spin angle,
drawn up to the current angle, from data/frames_spin_phase090.csv.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
FR = os.path.join(ROOT, "animation_spin90")
CSV = os.path.join(ROOT, "data", "frames_spin_phase090.csv")
OUTV = os.path.join(ROOT, "spin_sun90.mp4")
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COL = {"A": "#2a78d6", "D4k": "#eb6834", "N4k": "#1baf7a"}
NAME = {"A": "Detailed (115k triangles)", "D4k": "Cheap, shape kept (4.8k)", "N4k": "Plain automatic reduction (4k)"}
FD = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
F = lambda s: ImageFont.truetype(os.path.join(FD, "DejaVuSans.ttf"), s)
FB = lambda s: ImageFont.truetype(os.path.join(FD, "DejaVuSans-Bold.ttf"), s)

rows = list(csv.DictReader(open(CSV)))
spins = sorted({int(float(r["spin_deg"])) for r in rows})
spins = [s for s in spins if s % 5 == 0]
flux = {v: np.array([float([r for r in rows if r["variant"] == v and int(float(r["spin_deg"])) == s][0]["flux"])
                     for s in spins]) for v in COL}
phase = np.mean([float(r["phase_deg"]) for r in rows])
YMAX = max(f.max() for f in flux.values()) * 1.08


def graph(k, w=1280, h=330, dpi=100):
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor=SURF)
    ax = fig.add_axes([0.07, 0.2, 0.9, 0.62]); ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
    for v, c in COL.items():
        ax.plot(spins, flux[v], color=c, lw=1, alpha=0.18)
        ax.plot(spins[:k + 1], flux[v][:k + 1], color=c, lw=2.2)
        ax.plot(spins[k], flux[v][k], "o", ms=7, color=c, mec=SURF, mew=1.2)
    ax.axvline(spins[k], color="#b9b8b0", lw=1)
    ax.set_xlim(0, 360); ax.set_ylim(0, YMAX); ax.set_xticks(range(0, 361, 60))
    ax.set_xlabel("spin angle (degrees)", color=INK2); ax.set_ylabel("brightness (arbitrary units)", color=INK2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK2)
    fig.text(0.07, 0.92, "Brightness against spin angle", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.07, 0.855, "faint line = the full curve; solid line = drawn up to the current spin angle", fontsize=9.5, color=INK2)
    fig.canvas.draw()
    im = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
    plt.close(fig)
    return im


def crop_box():
    im = np.asarray(Image.open(os.path.join(FR, "A_000.png")).convert("L"))
    # use all frames of the detailed model to find where the satellite ever appears
    ys, xs = [], []
    for s in spins[::6]:
        a = np.asarray(Image.open(os.path.join(FR, f"A_{s:03d}.png")).convert("L")) > 8
        yy, xx = np.where(a)
        if len(yy):
            ys += [yy.min(), yy.max()]; xs += [xx.min(), xx.max()]
    cy, cx = (min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2
    half = max(max(ys) - min(ys), max(xs) - min(xs)) / 2 * 1.12
    half = max(half, 60)
    h = im.shape[0]
    x0 = int(max(0, min(h - 2 * half, cx - half))); y0 = int(max(0, min(h - 2 * half, cy - half)))
    return (x0, y0, int(x0 + 2 * half), int(y0 + 2 * half))


box = crop_box()
tmp = tempfile.mkdtemp()
for k, s in enumerate(spins):
    c = Image.new("RGB", (1280, 410 + 330), (252, 252, 251))
    d = ImageDraw.Draw(c)
    for j, v in enumerate(COL):
        im = Image.open(os.path.join(FR, f"{v}_{s:03d}.png")).convert("RGB").crop(box).resize((426, 340), Image.LANCZOS)
        c.paste(im, (j * 427, 0))
        d.rectangle([j * 427, 340, j * 427 + 426, 372], fill=(252, 252, 251))
        d.rectangle([j * 427 + 10, 350, j * 427 + 24, 364], fill=COL[v])
        d.text((j * 427 + 32, 348), NAME[v], font=FB(14), fill=(11, 11, 11))
    d.text((10, 378), f"Satellite spins about its vertical axis. Sun and camera stay fixed (Sun-camera angle about {phase:.0f}°).   "
                      f"Spin: {s:3d}°", font=F(14), fill=(82, 81, 78))
    c.paste(graph(k), (0, 410))
    c.save(os.path.join(tmp, f"f{k:03d}.png"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "f%03d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", OUTV], check=True)
shutil.rmtree(tmp)
print("video", round(os.path.getsize(OUTV) / 1e6, 2), "MB", len(spins), "frames")
