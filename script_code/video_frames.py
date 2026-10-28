"""
video_frames.py - render the pictures for the two explainer videos, and encode finished videos.

  1. stable_vs_tumbling : Aqua through the dawn-dusk pass three ways (stable / slow spin / tumbling), seen from
                          the ground observer.  Same geometry as light_curves.py's pass, so the brightness curve
                          drawn under the pictures is the measured data for exactly these moments.
  2. telescope_view     : Aqua spinning about one axis (Sun 90 deg from the observer), the spin from
                          light_curves.py's spin library whose brightness changes the most.

The pictures are for looking at, not measuring: a faint fill light (AMBIENT) is added so the dark side of
the satellite is not pure black, and the normal colour management is used.  The brightness curves in the
videos come from light_curves/data (no fill light, linear), not from these pictures.

Pipeline (make_videos.py lays the pictures and graphs out; Blender turns the frames into an MP4, since this
machine has no ffmpeg):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\video_frames.py", run_name="vf")
  ns["render_all"]()                                    # resumable; ~600 renders
  python script_code/make_videos.py                     (outside Blender) -> videos/composed/<name>/
  ns["encode"]("stable_vs_tumbling"); ns["encode"]("telescope_view")   -> videos/<name>.mp4
Needs light_curves.py to have been run first (it supplies the spin axis and the brightness data).
"""
import csv
import math
import os
import runpy
import time

import bpy
from mathutils import Matrix, Vector

HERE = r"C:\SSA\FYProject_SSA_Training\script_code"
ROOT = r"C:\SSA\FYProject_SSA_Training"
OUT = os.path.join(ROOT, "videos")
FRAMES = os.path.join(OUT, "frames")          # raw renders (ignored by git)
COMPOSED = os.path.join(OUT, "composed")      # laid-out video frames from make_videos.py (ignored by git)
RES = (640, 640)
SAMPLES = 32
AMBIENT = 0.03                                 # faint fill so the shape stays visible (pictures only)
FRAMING = 1.05
FPS = {"stable_vs_tumbling": 10, "telescope_view": 6}
SPIN_PHASE = 90


def _ns(name):
    return runpy.run_path(os.path.join(HERE, name), run_name="vf_" + name)


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def _az_el(v):
    v = v.normalized()
    return math.degrees(math.atan2(v.y, v.x)) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, v.z))))


def _shot(name, sun, cam, rot):
    s_az, s_el = _az_el(sun)
    c_az, c_el = _az_el(cam)
    return dict(name=name, sun_az=s_az, sun_el=s_el, cam_az=c_az, cam_el=c_el, rot_euler=tuple(rot.to_euler('XYZ')))


def pass_shots():
    """{case: [shots]}: the light_curves.py pass, with the satellite really turned (not the Sun and camera)."""
    lc = _ns("light_curves.py")
    frames, _ = _ns("dawn_dusk_scenario.py")["compute_pass"](lc["PASS_FRAMES"])
    out = {}
    for case in ("stable", "slow_spin", "tumble"):
        shots = []
        for f in frames:
            if case == "stable":
                rot = Matrix.Identity(3)
            elif case == "slow_spin":
                rot = Matrix.Rotation(math.radians(lc["SLOW_SPIN_DEG_S"] * f["t"]), 3, 'Z')
            else:
                rot = Matrix.Rotation(math.radians(lc["TUMBLE_DEG_S"] * f["t"]), 3, lc["TUMBLE_AXIS"])
            shots.append(_shot(f"{case}_{f['i']:04d}", _dir(f["sun_az"], f["sun_el"]), _dir(f["cam_az"], f["cam_el"]), rot))
        out[case] = shots
    return out


def chosen_axis():
    """The spin axis (index, vector) whose light curve varies most at SPIN_PHASE, from light_curves/data/spin_A.csv."""
    path = os.path.join(ROOT, "light_curves", "data", "spin_A.csv")
    if not os.path.exists(path):
        raise RuntimeError("Run light_curves.py first: telescope_view uses its spin data.")
    by = {}
    for r in csv.DictReader(open(path)):
        if int(r["phase_set_deg"]) == SPIN_PHASE:
            by.setdefault(int(r["axis_i"]), []).append(r)

    def variation(rows):
        b = [max(float(r["brightness"]), 1e-9) for r in rows]
        lb = [math.log10(x) for x in b]
        m = sum(lb) / len(lb)
        return sum((x - m) ** 2 for x in lb)
    i = max(by, key=lambda k: variation(by[k]))
    r0 = by[i][0]
    return i, Vector((float(r0["axis_x"]), float(r0["axis_y"]), float(r0["axis_z"])))


def spin_shots():
    lc = _ns("light_curves.py")
    i, axis = chosen_axis()
    obs = Vector((1.0, 0.0, 0.0))
    sun = Vector((math.cos(math.radians(SPIN_PHASE)), math.sin(math.radians(SPIN_PHASE)), 0.0))
    shots = [_shot(f"spin_{th:03d}", sun, obs, Matrix.Rotation(math.radians(th), 3, axis))
             for th in range(0, 360, lc["SPIN_STEP"])]
    return i, shots


def _render(folder, shots, max_seconds, t0):
    ra = _ns("render_angles.py")
    aqua = [m for m in ra["MODELS"] if m["label"] == "Aqua_detailed"]
    os.makedirs(folder, exist_ok=True)
    todo = [s for s in shots if not os.path.exists(os.path.join(folder, s["name"] + ".png"))]
    for k in range(0, len(todo), 8):
        if time.perf_counter() - t0 > max_seconds:
            break
        ra["main"](out_dir=folder, shots=todo[k:k + 8], models=aqua, res=RES, samples=SAMPLES, framing=FRAMING,
                   filename=lambda lbl, i, shot: shot["name"] + ".png", write_log=False, ambient=AMBIENT)
    return sum(1 for s in shots if not os.path.exists(os.path.join(folder, s["name"] + ".png")))


def render_all(max_seconds=3 * 3600):
    """Render whichever frames are still missing for both videos."""
    t0 = time.perf_counter()
    left = 0
    for case, shots in pass_shots().items():
        left += _render(os.path.join(FRAMES, "stable_vs_tumbling"), shots, max_seconds, t0)
    axis_i, shots = spin_shots()
    left += _render(os.path.join(FRAMES, "telescope_view"), shots, max_seconds, t0)
    with open(os.path.join(FRAMES, "telescope_view", "axis.txt"), "w") as fh:
        fh.write(f"{axis_i}\n")
    return dict(remaining=left, seconds=round(time.perf_counter() - t0, 1), telescope_axis=axis_i)


def encode(name):
    """Join videos/composed/<name>/f0001.png ... into videos/<name>.mp4 with Blender's video sequencer."""
    folder = os.path.join(COMPOSED, name)
    files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    if not files:
        raise RuntimeError(f"No composed frames in {folder}: run make_videos.py first.")
    img = bpy.data.images.load(os.path.join(folder, files[0]))
    w, h = img.size
    bpy.data.images.remove(img)
    sname = "SSA_Encode"
    if sname in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes[sname])
    sc = bpy.data.scenes.new(sname)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.fps = FPS[name]
    sc.frame_start, sc.frame_end = 1, len(files)
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    s = strips.new_image("frames", filepath=os.path.join(folder, files[0]), channel=1, frame_start=1)
    for f in files[1:]:
        s.elements.append(f)
    sc.view_settings.view_transform = 'Standard'       # the frames are finished pictures: no extra tone mapping
    sc.view_settings.look = 'None'
    r = sc.render
    r.use_sequencer = True
    if hasattr(r.image_settings, "media_type"):      # Blender 5+: pick "video" before the FFMPEG format
        r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    video = os.path.join(OUT, name + ".mp4")
    r.filepath = video
    bpy.ops.render.render(animation=True, scene=sname)
    bpy.data.scenes.remove(sc)
    # Blender may add a frame range to the name (e.g. name0001-0096.mp4): rename it to the plain name
    stem = name
    for f in os.listdir(OUT):
        if f.startswith(stem) and f.endswith(".mp4") and f != stem + ".mp4":
            if os.path.exists(video):
                os.remove(video)
            os.replace(os.path.join(OUT, f), video)
    return dict(video=video, frames=len(files), fps=FPS[name], size_mb=round(os.path.getsize(video) / 1e6, 2))
