"""
light_curves.py - light curves (brightness over time) for two questions that single snapshots cannot answer.

1. SPIN LIBRARY: does a sequence of measurements pin down how a satellite is spinning?
   Each satellite spins through 360 degrees about each of N_AXES spin axes (spread evenly over the sphere),
   in SPIN_STEP-degree steps, while the Sun and the observer stay fixed, at three Sun-observer phase angles.
   The plots compare every axis with every other: how many different spin axes give the same stretch of
   light curve, as the stretch gets longer?  (Brightness map = one snapshot; this = a sequence.)

2. STABLE vs TUMBLING on a real-looking pass: the dawn-dusk pass from dawn_dusk_scenario.py, rendered for
     stable     Earth-pointing, as Aqua and Suomi NPP really fly (body frame = local orbit frame)
     slow_spin  spinning about its own up axis at 0.8 deg/s (the old animation's setting)
     tumble     tumbling about a tilted axis once a minute (6 deg/s), like a dead satellite or debris

Brightness is measured exactly as in brightness_map.py (orthographic camera, sum of linear pixel luminance x
pixel area), using its scene builder, so the numbers can be compared directly.  Instead of turning the
satellite, the Sun and observer directions are turned the opposite way in the satellite's body frame; the
picture is the same.

Resumable: each finished spin (one axis at one phase) or pass case is saved straight away.
Usage (Blender console, or TEST = "light_curves" in run_tests.py):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\light_curves.py", run_name="lc")
  ns["run"]()            # about 35 minutes for both satellites; stops after max_seconds, run again to continue
Then, outside Blender:  python plots/plot_light_curves.py
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
OUT_DIR = os.path.join(ROOT, "light_curves")
OBJECTS = ("A", "C")                 # Aqua detailed, Suomi NPP low-poly (as in brightness_map.py)
N_AXES = 24                          # spin axes, about 40 degrees apart
SPIN_STEP = 10                       # degrees per frame -> 36 frames per turn
PHASES = (30, 90, 150)               # Sun-observer angle for the spin library
PASS_FRAMES = 96                     # frames over the dawn-dusk pass (about 5 s apart)
SLOW_SPIN_DEG_S = 0.8                # about the satellite's up (+Z) axis
TUMBLE_DEG_S = 6.0                   # one turn a minute
TUMBLE_AXIS = Vector((1.0, 1.0, 1.0)).normalized()

SPIN_HEADER = ["object", "axis_i", "axis_x", "axis_y", "axis_z", "phase_set_deg", "frame", "spin_deg",
               "brightness", "pixel_sum", "pixel_area_m2", "border_alpha"]
PASS_HEADER = ["object", "case", "frame", "t_s", "phase_deg", "range_km", "obs_elev_deg", "brightness",
               "pixel_sum", "pixel_area_m2", "border_alpha"]


def _bm():
    return runpy.run_path(os.path.join(HERE, "brightness_map.py"), run_name="bmap")


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def _done(path, cols):
    """Set of tuples of the given columns already in a CSV (finished chunks)."""
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as fh:
        return {tuple(r[c] for c in cols) for r in csv.DictReader(fh)}


def _append(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(header)
        w.writerows(rows)


class _Shooter:
    """Renders one object for given body-frame Sun and observer directions."""

    def __init__(self, bm, sc, cam, sun, col, data_dir):
        self.bm, self.sc, self.cam, self.sun = bm, sc, cam, sun
        self.centre, self.radius, _ = bm["_bounds"](col)
        cam.data.ortho_scale = 2.0 * self.radius * 1.03
        self.dist = self.radius * 4.0 + 1.0
        cam.data.clip_start, cam.data.clip_end = 0.01, self.dist + self.radius * 2.0 + 10.0
        self.pix_area = (cam.data.ortho_scale / bm["RES"]) ** 2
        self.tmp = os.path.join(data_dir, "_tmp")

    def shoot(self, s, o):
        s, o = s.normalized(), o.normalized()
        self.sun.location = self.centre + s * self.dist * 2
        self.bm["look_along"](self.sun, -s)
        self.cam.location = self.centre + o * self.dist
        self.bm["look_along"](self.cam, -o)
        bpy.context.view_layer.update()
        flux, edge = self.bm["_render"](self.sc, self.tmp)
        return flux * self.pix_area, flux, edge


def _check_not_black(rows, col, what):
    if max(r[col] for r in rows) == 0.0:
        raise RuntimeError(f"{what}: every render came out black. The graphics driver has probably failed: "
                           "restart Blender and run again (nothing was saved for this part).")


def run(objects=OBJECTS, max_seconds=4 * 3600, out_dir=OUT_DIR):
    t0 = time.perf_counter()
    bm = _bm()
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    axes = bm["fibonacci_directions"](N_AXES)
    angles = list(range(0, 360, SPIN_STEP))
    obs_in = Vector((1.0, 0.0, 0.0))                              # observer, fixed in space
    sc_ = runpy.run_path(os.path.join(HERE, "dawn_dusk_scenario.py"), run_name="scenario")
    frames, meta = sc_["compute_pass"](PASS_FRAMES)

    sc, cam, sun = bm["_new_scene"]()
    rendered, timed_out = 0, False
    try:
        for key in objects:
            col, undo = bm["_attach"](sc, key)
            try:
                sh = _Shooter(bm, sc, cam, sun, col, data_dir)

                # --- 1. spin library
                path = os.path.join(data_dir, f"spin_{key}.csv")
                done = _done(path, ("axis_i", "phase_set_deg"))
                for ph in PHASES:
                    sun_in = Vector((math.cos(math.radians(ph)), math.sin(math.radians(ph)), 0.0))
                    for i, ax in enumerate(axes):
                        if (str(i), str(ph)) in done:
                            continue
                        if time.perf_counter() - t0 > max_seconds:
                            timed_out = True
                            break
                        rows = []
                        for f, th in enumerate(angles):
                            back = Matrix.Rotation(math.radians(-th), 3, ax)   # space -> body after turning th
                            b, flux, edge = sh.shoot(back @ sun_in, back @ obs_in)
                            rendered += 1
                            rows.append([key, i, round(ax.x, 5), round(ax.y, 5), round(ax.z, 5), ph, f, th,
                                         b, flux, sh.pix_area, edge])
                        _check_not_black(rows, 9, f"{key} spin axis {i}, phase {ph}")
                        _append(path, SPIN_HEADER, rows)
                    if timed_out:
                        break
                    print(f"[light_curves] {key}: spin library, phase {ph} done ({time.perf_counter() - t0:.0f} s)")

                # --- 2. stable vs tumbling over the dawn-dusk pass
                path = os.path.join(data_dir, f"pass_{key}.csv")
                done = _done(path, ("case",))
                for case in ("stable", "slow_spin", "tumble"):
                    if timed_out or (case,) in done:
                        continue
                    if time.perf_counter() - t0 > max_seconds:
                        timed_out = True
                        break
                    rows = []
                    for f in frames:
                        s_loc, o_loc = _dir(f["sun_az"], f["sun_el"]), _dir(f["cam_az"], f["cam_el"])
                        if case == "stable":
                            back = Matrix.Identity(3)
                        elif case == "slow_spin":
                            back = Matrix.Rotation(math.radians(-SLOW_SPIN_DEG_S * f["t"]), 3, 'Z')
                        else:
                            back = Matrix.Rotation(math.radians(-TUMBLE_DEG_S * f["t"]), 3, TUMBLE_AXIS)
                        b, flux, edge = sh.shoot(back @ s_loc, back @ o_loc)
                        rendered += 1
                        rows.append([key, case, f["i"], round(f["t"], 2), round(f["phase"], 2),
                                     round(f["range_km"], 1), round(f["obs_elev"], 2), b, flux, sh.pix_area, edge])
                    _check_not_black(rows, 8, f"{key} pass, {case}")
                    _append(path, PASS_HEADER, rows)
                    print(f"[light_curves] {key}: pass '{case}' done ({time.perf_counter() - t0:.0f} s)")
            finally:
                undo()
            if timed_out:
                break
    finally:
        bpy.data.scenes.remove(sc)
        for name in ("BM_cam", "BM_sun"):
            if name in bpy.data.objects:
                bpy.data.objects.remove(bpy.data.objects[name])

    remaining = 0
    for key in objects:
        remaining += len(PHASES) * N_AXES - len(_done(os.path.join(data_dir, f"spin_{key}.csv"), ("axis_i", "phase_set_deg")))
        remaining += 3 - len(_done(os.path.join(data_dir, f"pass_{key}.csv"), ("case",)))
    return dict(rendered_this_call=rendered, seconds=round(time.perf_counter() - t0, 1), remaining=remaining,
                data=data_dir)
