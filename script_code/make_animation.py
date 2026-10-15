"""
make_animation.py - animate the dawn-dusk pass as a side-by-side video (detailed vs low-poly).

  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\make_animation.py", run_name="anim")
  ns["render_frames"](max_seconds=100)   # repeat until it reports remaining == 0 (resumable)
  ns["assemble"]()                      # builds the MP4 from the rendered frames

Every frame uses the same geometry as dawn_dusk_scenario.py (Sun, observer and spin for that
moment of the pass), just sampled densely.  The 8.3-minute pass is compressed into SECONDS of video.
"""
import os
import time
import runpy
import bpy

FPS = 24
SECONDS = 10                       # video length; the 497 s pass is played back faster than real time
N = FPS * SECONDS
RES = (1280, 720)                  # per satellite; the video is twice as wide
FRAMES_DIR = r"C:\SSA\animation_frames_v2"   # outside the repo (hundreds of MB of PNGs)
VIDEO = r"C:\SSA\FYProject_SSA_Training\dawn_dusk_pass.mp4"
FRAMING = 1.05
LABELS = {"Aqua_detailed": "Aqua  -  detailed (115k triangles)",
          "SuomiNPP_lowpoly": "Suomi NPP  -  low-poly (4k triangles)"}

_here = os.path.dirname(os.path.abspath(globals().get("__file__", "")))
if not os.path.exists(os.path.join(_here, "render_angles.py")):
    _here = r"C:\SSA\FYProject_SSA_Training\script_code"


def _load():
    ra = runpy.run_path(os.path.join(_here, "render_angles.py"), run_name="render_angles")
    sc = runpy.run_path(os.path.join(_here, "dawn_dusk_scenario.py"), run_name="scenario")
    frames, meta = sc["compute_pass"](N)
    return ra, frames, meta


def _frame_path(label, i):
    return os.path.join(FRAMES_DIR, label, f"frame_{i:04d}.png")


def render_frames(max_seconds=100, engine="EEVEE", samples=64, batch=8):
    """Render whichever frames are still missing, stopping after about max_seconds."""
    t0 = time.perf_counter()
    ra, frames, meta = _load()
    done_now = 0
    for model in ra["MODELS"]:
        label = model["label"]
        os.makedirs(os.path.join(FRAMES_DIR, label), exist_ok=True)
        todo = [f for f in frames if not os.path.exists(_frame_path(label, f["i"]))]
        for k in range(0, len(todo), batch):
            if time.perf_counter() - t0 > max_seconds:
                break
            chunk = todo[k:k + batch]
            shots = [dict(name=f"frame_{f['i']:04d}", sun_az=f["sun_az"], sun_el=f["sun_el"],
                          cam_az=f["cam_az"], cam_el=f["cam_el"], rot_x=0, rot_z=f["spin"])
                     for f in chunk]
            ra["main"](out_dir=os.path.join(FRAMES_DIR, label), engine=engine, shots=shots,
                       models=[model], res=RES, samples=samples, framing=FRAMING,
                       filename=lambda lbl, i, shot: shot["name"] + ".png", write_log=False)
            done_now += len(chunk)
    remaining = sum(1 for m in ra["MODELS"] for f in frames
                    if not os.path.exists(_frame_path(m["label"], f["i"])))
    return dict(rendered_this_call=done_now, remaining=remaining, total=N * len(ra["MODELS"]),
                seconds=round(time.perf_counter() - t0, 1))


def assemble(video=VIDEO):
    """Join the rendered frames into one side-by-side MP4 using Blender's video sequencer."""
    ra, frames, meta = _load()
    labels = [m["label"] for m in ra["MODELS"]]
    missing = [(l, f["i"]) for l in labels for f in frames if not os.path.exists(_frame_path(l, f["i"]))]
    if missing:
        raise RuntimeError(f"{len(missing)} frames not rendered yet (first missing: {missing[0]})")

    name = "SSA_Video"
    if name in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes[name])
    sc = bpy.data.scenes.new(name)
    sc.render.resolution_x, sc.render.resolution_y = RES[0] * 2, RES[1]
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, N
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences

    for ch, (label, off) in enumerate(zip(labels, (-RES[0] / 2, RES[0] / 2)), start=1):
        first = _frame_path(label, 1)
        s = strips.new_image(label, filepath=first, channel=ch, frame_start=1)
        for i in range(2, N + 1):
            s.elements.append(os.path.basename(_frame_path(label, i)))
        s.transform.offset_x = off
        s.transform.offset_y = 0

    def text(strip_name, channel, start, end, body, x, y, size, color):
        t = strips.new_effect(name=strip_name, type='TEXT', channel=channel,
                              frame_start=start, length=end - start)
        t.text, t.font_size, t.color = body, size, color
        t.location = (x, y)
        t.use_shadow = True
        return t

    text("label_left", 4, 1, N + 1, LABELS[labels[0]], 0.25, 0.94, 30, (1, 1, 1, 1))
    text("label_right", 5, 1, N + 1, LABELS[labels[1]], 0.75, 0.94, 30, (1, 1, 1, 1))
    for f in frames:
        body = (f"pass time {f['t']:3.0f} s   |   observer elevation {f['obs_elev']:2.0f} deg   |   "
                f"Sun phase angle {f['phase']:3.0f} deg   |   spin {f['spin']:3.0f} deg")
        text(f"info_{f['i']}", 6, f["i"], f["i"] + 1, body, 0.5, 0.05, 24, (1, 0.92, 0.6, 1))

    r = sc.render
    r.use_sequencer = True
    if hasattr(r.image_settings, "media_type"):      # Blender 5+: pick "video" before the FFMPEG format
        r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'MEDIUM'
    r.filepath = video
    os.makedirs(os.path.dirname(video), exist_ok=True)
    bpy.ops.render.render(animation=True, scene=name)
    bpy.data.scenes.remove(sc)
    # Blender may add a frame range to the name (e.g. dawn_dusk_pass0001-0240.mp4): find what it wrote
    folder, stem = os.path.dirname(video), os.path.splitext(os.path.basename(video))[0]
    written = sorted(f for f in os.listdir(folder) if f.startswith(stem) and f.endswith(".mp4"))
    paths = [os.path.join(folder, f) for f in written]
    return dict(videos=paths, size_mb=[round(os.path.getsize(p) / 1e6, 2) for p in paths],
                frames=N, fps=FPS, seconds=SECONDS)
