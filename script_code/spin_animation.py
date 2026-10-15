"""
spin_animation.py - render the frames for the "spin, Sun 90 deg" animation (fidelity test, top-right graph).

The satellite spins 360 degrees about its vertical axis; the Sun and the camera stay fixed.
Three versions of Aqua are shown at identical angles:
    A    detailed (115k triangles)
    D4k  cheap, shape kept (~4.8k triangles)
    N4k  plain automatic reduction (4k triangles)
It reuses the scene builder from fidelity_test.py (same models, same Sun, same orthographic camera), so the
pictures match the brightness numbers in fidelity_test/data/frames_spin_phase090.csv.

Run (Blender console / Scripting tab):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\spin_animation.py", run_name="spin")
  ns["run"]()         # resumable: frames that already exist are skipped
Then run make_spin_animation.py (any Python with Pillow, matplotlib, numpy, ffmpeg) to build the video.
"""
import math
import os
import runpy

import bpy

HERE = r"C:\SSA\FYProject_SSA_Training"
OUT = os.path.join(HERE, "fidelity_test", "animation_spin90")
VARIANTS = ["A", "D4k", "N4k"]
PHASE = 90                      # Sun azimuth offset from the camera (same as the fidelity test's "spin, 90")
STEP = 5                        # degrees of spin per frame (72 frames)
RES = 720
SAMPLES = 32


def frame_path(variant, spin):
    return os.path.join(OUT, f"{variant}_{int(spin):03d}.png")


def run(max_seconds=900):
    import time
    t0 = time.perf_counter()
    spins = list(range(0, 360, STEP))
    todo = [(v, s) for s in spins for v in VARIANTS if not os.path.exists(frame_path(v, s))]
    if not todo:
        return dict(done=True, remaining=0)
    os.makedirs(OUT, exist_ok=True)
    ft = runpy.run_path(os.path.join(HERE, "fidelity_test.py"), run_name="fid")
    sc, V, cam, sun, restore, info = ft["build_scene"]()
    sc.render.resolution_x = sc.render.resolution_y = RES
    try:
        sc.eevee.taa_render_samples = SAMPLES
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.film_transparent = False
    cam_az, cam_el = ft["CAM_AZ"], ft["CAM_EL"]
    sd, cd = ft["direction"](cam_az + PHASE, cam_el), ft["direction"](cam_az, cam_el)
    sun.location = sd * 100
    ft["look_along"](sun, -sd)
    cam.location = cd * 100
    ft["look_along"](cam, -cd)
    done = 0
    try:
        for s in spins:
            for v in VARIANTS:
                if not os.path.exists(frame_path(v, s)):
                    if time.perf_counter() - t0 > max_seconds:
                        raise StopIteration
                    for k in V:
                        V[k]["col"].hide_render = (k != v)
                        V[k]["spin"].rotation_euler = (0, 0, math.radians(s))
                    cam.data.ortho_scale = 2.0 * V["A"]["radius"] * 1.03      # same scale for all three
                    bpy.context.view_layer.update()
                    sc.render.filepath = frame_path(v, s)
                    bpy.ops.render.render(scene=sc.name, write_still=True)
                    done += 1
    except StopIteration:
        pass
    finally:
        ft["cleanup"](restore)
    remaining = sum(1 for s in spins for v in VARIANTS if not os.path.exists(frame_path(v, s)))
    return dict(rendered_this_call=done, remaining=remaining, total=len(spins) * len(VARIANTS),
                seconds=round(time.perf_counter() - t0, 1))


if __name__ == "__main__":
    print(run())
