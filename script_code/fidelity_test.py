"""
fidelity_test.py - how much does model detail matter for brightness at orbital distance?

VARIANTS (all rendered at identical Sun / camera / spin angles)
  A        Aqua detailed (your 115k-triangle model) - the reference
  N4k      Aqua, plain automatic decimation to ~4k triangles (shrinks thin flat parts: a BAD cheap model)
  D30k/D10k/D5k/D4k  Aqua reduced to ~30k / 10k / 5k / 4k triangles with the thin flat parts (solar
                   arrays, panels, antennas) kept whole and only the bulky body parts simplified
  C        Suomi NPP low-poly (your supplied low-poly model - a different satellite, so shape differs too)

WHAT IS MEASURED
  * brightness  = total linear light reaching the camera (sum of pixel luminance, 32-bit EXR)
  * the camera is ORTHOGRAPHIC: at orbital range the rays from the satellite are parallel
  * washout: the picture is summed into blocks of k x k pixels (k = 1, 2, 4 ... 512).  Big blocks mimic a
    distant object / coarse sensor.  E(k) = sum|A_k - B_k| / sum(A_k) is the fractional brightness
    difference between detailed and decimated that survives at that resolution.  k = 512 is the
    whole picture in one pixel, i.e. a point source: E = |flux_B - flux_A| / flux_A.

GEOMETRIES
  spin sweeps  : the satellite spins about its vertical (Z) axis, Sun and camera fixed in the satellite
                 frame, at Sun-camera phase angles 30, 90 and 150 deg (5 deg steps)
  dawn-dusk    : the 48-frame pass from dawn_dusk_scenario.py (Sun, observer and spin change together)

Usage (Blender console):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\fidelity_test.py", run_name="fid")
  ns["run"]()            # resumable: finished geometries are skipped
"""
import csv
import math
import os
import runpy
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = r"C:\SSA\FYProject_SSA_Training\script_code"        # folder holding these scripts
ROOT = r"C:\SSA\FYProject_SSA_Training"   # project root: renders, data and videos go here
OUT_DIR = os.path.join(ROOT, "fidelity_test")
RES = 512
SAMPLES = 16
SUN_STRENGTH = 4.0
SPIN_STEP = 5
PHASES = (30, 90, 150)
CAM_AZ, CAM_EL = 0.0, 20.0
PASS_FRAMES = 48
LEVELS = [2 ** i for i in range(10)]          # block sizes 1 ... 512
TARGET_TRIS = 4024                            # the supplied low-poly model's triangle count
SCENE = "SSA_Fidelity"

MODELS = {"A": dict(collection="Satellite_Detailed", root="Aqua_Detailed_root"),
          "C": dict(collection="Satellite_LowPoly", root="SuomiNPP_LowPoly_root")}


def direction(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def look_along(obj, vec):
    obj.rotation_euler = vec.normalized().to_track_quat('-Z', 'Y').to_euler()


def tri_count(objs_or_meshes):
    n = 0
    for o in objs_or_meshes:
        me = o.data if hasattr(o, "data") else o
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
    return n


def _co(me):
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(n, 3).astype(np.float64)


def world_bbox(pairs):
    pts = []
    for me, mw in pairs:
        if len(me.vertices):
            m = np.array(mw)
            pts.append(_co(me) @ m[:3, :3].T + m[:3, 3])
    p = np.concatenate(pts)
    return Vector(p.min(axis=0)), Vector(p.max(axis=0))


def world_area(pairs):
    tot = 0.0
    for me, mw in pairs:
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if nt == 0:
            continue
        m = np.array(mw)
        w = _co(me) @ m[:3, :3].T + m[:3, 3]
        t = np.empty(nt * 3, dtype=np.int32)
        me.loop_triangles.foreach_get("vertices", t)
        t = t.reshape(-1, 3)
        tot += 0.5 * np.linalg.norm(np.cross(w[t[:, 1]] - w[t[:, 0]], w[t[:, 2]] - w[t[:, 0]]), axis=1).sum()
    return float(tot)


# ---------------------------------------------------------------------------------------
# scene construction
# ---------------------------------------------------------------------------------------
KEEP = 800          # parts with at most this many triangles (flat panels, arrays, antennas) are kept whole


def _source_meshes(key):
    m = MODELS[key]
    pivot = bpy.data.objects.get(m["root"].replace("_root", "_pivot"))
    old_rot = tuple(pivot.rotation_euler) if pivot else None
    if pivot:
        pivot.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    col = bpy.data.collections[m["collection"]]
    objs = [o for o in col.all_objects if o.type == 'MESH' and not o.hide_render]
    return [(o, o.matrix_world.copy()) for o in objs], (pivot, old_rot)


class _Reducer:
    """Temporary copies of the source parts with a planar-merge and/or collapse modifier."""

    def __init__(self, pairs):
        self.pairs = pairs
        self.col = bpy.data.collections.new("FID_tmp")
        bpy.context.scene.collection.children.link(self.col)
        self.copies = []
        for o, mw in pairs:
            c = o.copy()
            c.parent = None
            c.matrix_world = mw
            self.col.objects.link(c)
            self.copies.append(c)

    def evaluate(self, planar, ratios):
        """planar: merge flat faces first; ratios: per-part collapse ratio (None = no collapse)."""
        for c, r in zip(self.copies, ratios):
            for md in list(c.modifiers):
                c.modifiers.remove(md)
            if planar:
                d = c.modifiers.new("planar", 'DECIMATE')
                d.decimate_type = 'DISSOLVE'
                d.angle_limit = math.radians(2.0)
                d.delimit = {'MATERIAL'}
            if r is not None and r < 1.0:
                d = c.modifiers.new("collapse", 'DECIMATE')
                d.decimate_type = 'COLLAPSE'
                d.ratio = r
                d.use_collapse_triangulate = True
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        return [bpy.data.meshes.new_from_object(c.evaluated_get(dg), depsgraph=dg) for c in self.copies]

    def close(self):
        for c in self.copies:
            bpy.data.objects.remove(c)
        bpy.data.collections.remove(self.col)


def _reduce(red, planar, target, protect):
    """Return (meshes, total triangles).  target=None: planar merge only."""
    none = [None] * len(red.copies)
    if target is None:
        ms = red.evaluate(planar, none)
        return ms, tri_count(ms)
    if not protect:                                           # naive: one ratio for everything
        n0 = tri_count([o for o, _ in red.pairs])
        r = target / n0
        best = None
        for _ in range(4):
            ms = red.evaluate(False, [r] * len(none))
            tot = tri_count(ms)
            if best:
                [bpy.data.meshes.remove(m) for m in best[0]]
            best = (ms, tot)
            if abs(tot - target) / target < 0.05:
                break
            r = min(1.0, r * target / max(1, tot))
        return best
    base = red.evaluate(planar, none)
    n = [tri_count([m]) for m in base]
    [bpy.data.meshes.remove(m) for m in base]
    prot = sum(x for x in n if x <= KEEP)
    big = sum(x for x in n if x > KEEP)
    r = max(0.001, min(1.0, (target - prot) / max(1, big)))
    best = None
    for _ in range(5):
        ms = red.evaluate(planar, [r if x > KEEP else None for x in n])
        tot = tri_count(ms)
        if best:
            [bpy.data.meshes.remove(m) for m in best[0]]
        best = (ms, tot)
        if abs(tot - target) / target < 0.05:
            break
        got_big = sum(tri_count([m]) for m, x in zip(ms, n) if x > KEEP)
        r = max(0.001, min(1.0, r * (target - prot) / max(1, got_big)))
    return best


VARIANT_ORDER = ["A", "N4k", "D30k", "D10k", "D5k", "D4k", "C"]
PICTURE_VARIANTS = ["A", "N4k", "D4k"]


def build_scene():
    if SCENE in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes[SCENE])
    sc = bpy.data.scenes.new(SCENE)
    restore = []
    srcA, rA = _source_meshes("A")
    srcC, rC = _source_meshes("C")
    restore += [rA, rC]
    sets = {"A": [(o.data, mw) for o, mw in srcA], "C": [(o.data, mw) for o, mw in srcC]}
    red = _Reducer(srcA)
    try:
        for name, planar, target, protect in (("N4k", False, TARGET_TRIS, False), ("D30k", False, 30000, True),
                                     ("D10k", False, 10000, True), ("D5k", False, 5000, True),
                                     ("D4k", False, TARGET_TRIS, True)):
            ms, tot = _reduce(red, planar, target, protect)
            sets[name] = [(m, mw) for m, (_, mw) in zip(ms, srcA)]
    finally:
        red.close()

    info = {}
    centres, radii = {}, {}
    for k in ("A", "C"):
        mn, mx = world_bbox(sets[k])
        centres[k], radii[k] = (mn + mx) / 2, (mx - mn).length / 2
        info["extent_" + k] = tuple(round(v, 3) for v in (mx - mn))
    areaA = world_area(sets["A"])
    V = {}
    for k in VARIANT_ORDER:
        base = "C" if k == "C" else "A"
        col = bpy.data.collections.new("FID_" + k)
        sc.collection.children.link(col)
        spin = bpy.data.objects.new("FID_spin_" + k, None)
        col.objects.link(spin)
        for i, (me, mw) in enumerate(sets[k]):
            ob = bpy.data.objects.new(f"FID_{k}_{i}", me)
            ob.matrix_world = Matrix.Translation(-centres[base]) @ mw
            col.objects.link(ob)
            ob.parent = spin
            ob.matrix_parent_inverse = Matrix.Identity(4)
        V[k] = dict(col=col, spin=spin, radius=radii[base], tris=tri_count([m for m, _ in sets[k]]),
                    area=world_area(sets[k]))
    info["variants"] = {k: dict(tris=V[k]["tris"], area=round(V[k]["area"], 3),
                                area_vs_A=round(V[k]["area"] / areaA, 4)) for k in V if k != "C"}
    info["variants"]["C"] = dict(tris=V["C"]["tris"], area=round(V["C"]["area"], 3))

    cam = bpy.data.objects.new("FID_cam", bpy.data.cameras.new("FID_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.clip_start, cam.data.clip_end = 0.1, 1000
    sun = bpy.data.objects.new("FID_sun", bpy.data.lights.new("FID_sun", 'SUN'))
    sc.collection.objects.link(sun)
    sun.data.energy = SUN_STRENGTH
    sun.data.angle = math.radians(0.53)

    w = bpy.data.worlds.get("FID_black") or bpy.data.worlds.new("FID_black")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.world = w

    r = sc.render
    for cand in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            r.engine = cand
            break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = SAMPLES
    except Exception:
        pass
    r.resolution_x = r.resolution_y = RES
    r.resolution_percentage = 100
    r.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    r.image_settings.file_format = 'OPEN_EXR'
    r.image_settings.color_depth = '32'
    return sc, V, cam, sun, restore, info


def cleanup(restore):
    for pivot, rot in restore:
        if pivot is not None and rot is not None:
            pivot.rotation_euler = rot
    if SCENE in bpy.data.scenes:
        sc = bpy.data.scenes[SCENE]
        objs = [o for c in sc.collection.children_recursive for o in c.objects] + list(sc.collection.objects)
        bpy.data.scenes.remove(sc)
        for o in set(objs):
            bpy.data.objects.remove(o)
        for c in [c for c in bpy.data.collections if c.name.startswith("FID_")]:
            bpy.data.collections.remove(c)
    for me in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------------------
# measuring
# ---------------------------------------------------------------------------------------
def render_lum(sc, tmp):
    sc.render.filepath = tmp
    bpy.ops.render.render(scene=sc.name, write_still=True)
    exr = tmp + ".exr"
    img = bpy.data.images.load(exr)
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    os.remove(exr)
    px = px.reshape(h, w, 4)
    lum = 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]
    a = px[..., 3]
    edge = float(a[0].sum() + a[-1].sum() + a[:, 0].sum() + a[:, -1].sum())
    return lum.astype(np.float64), edge


def binned(L, k):
    n = L.shape[0] // k
    return L.reshape(n, k, n, k).sum(axis=(1, 3))


def errors(A, B):
    out = []
    for k in LEVELS:
        a, b = binned(A, k), binned(B, k)
        s = a.sum()
        out.append(float(np.abs(a - b).sum() / s) if s > 0 else float("nan"))
    return out


def configs():
    cams = {}
    for ph in PHASES:
        cams[f"spin_phase{ph:03d}"] = [
            dict(sun_az=CAM_AZ + ph, sun_el=CAM_EL, cam_az=CAM_AZ, cam_el=CAM_EL, spin=s, t=None)
            for s in range(0, 360, SPIN_STEP)]
    ns = runpy.run_path(os.path.join(HERE, "dawn_dusk_scenario.py"), run_name="scenario")
    frames, meta = ns["compute_pass"](PASS_FRAMES)
    cams["dawn_dusk_pass"] = [dict(sun_az=f["sun_az"], sun_el=f["sun_el"], cam_az=f["cam_az"],
                                   cam_el=f["cam_el"], spin=f["spin"], t=f["t"]) for f in frames]
    return cams


def do_config(sc, V, cam, sun, name, geoms):
    os.makedirs(os.path.join(OUT_DIR, "data"), exist_ok=True)
    tmp = os.path.join(OUT_DIR, "data", "_tmp")
    rows, keep, secs = [], {}, {k: 0.0 for k in VARIANT_ORDER}
    for i, g in enumerate(geoms):
        sd, cd = direction(g["sun_az"], g["sun_el"]), direction(g["cam_az"], g["cam_el"])
        phase = math.degrees(math.acos(max(-1, min(1, sd.dot(cd)))))
        sun.location = sd * 100
        look_along(sun, -sd)
        cam.location = cd * 100
        look_along(cam, -cd)
        lum = {}
        for k in VARIANT_ORDER:
            for kk in VARIANT_ORDER:
                V[kk]["col"].hide_render = (kk != k)
                V[kk]["spin"].rotation_euler = (0, 0, math.radians(g["spin"]))
            cam.data.ortho_scale = 2.0 * V[k]["radius"] * 1.03
            bpy.context.view_layer.update()
            t0 = time.perf_counter()
            lum[k], edge = render_lum(sc, tmp)
            secs[k] += time.perf_counter() - t0
            if k == "A":
                edgeA = edge
        fluxA = lum["A"].sum()
        for k in VARIANT_ORDER:
            E = errors(lum["A"], lum[k]) if k not in ("A", "C") else [float("nan")] * len(LEVELS)
            rows.append([name, i, round(g["spin"], 3), round(phase, 2), k, V[k]["tris"], fluxA,
                         lum[k].sum(), edgeA] + E)
        keep[i] = (fluxA, {k: lum[k] for k in PICTURE_VARIANTS})
    order = sorted(keep, key=lambda j: keep[j][0])
    pick = [order[-1], order[int(len(order) * 0.5)]]
    arrays = {f"{k}_{n}": np.stack([keep[j][1][k] for j in pick]).astype(np.float16)
              for n, k in enumerate(PICTURE_VARIANTS)}
    np.savez_compressed(os.path.join(OUT_DIR, "data", f"pictures_{name}.npz"), idx=np.array(pick),
                        names=np.array(PICTURE_VARIANTS), **arrays)
    path = os.path.join(OUT_DIR, "data", f"frames_{name}.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["config", "frame", "spin_deg", "phase_deg", "variant", "triangles", "flux_A_reference",
                    "flux", "border_alpha_A"] + [f"E_block{k}" for k in LEVELS])
        w.writerows(rows)
    return dict(config=name, frames=len(geoms), seconds={k: round(v, 1) for k, v in secs.items()})


def run(only=None, force=False):
    import json
    cfgs = configs()
    names = [n for n in cfgs if (only is None or n in only)]
    todo = [n for n in names if force or not os.path.exists(os.path.join(OUT_DIR, "data", f"frames_{n}.csv"))]
    if not todo:
        return "all done"
    sc, V, cam, sun, restore, info = build_scene()
    info.update(res=RES, samples=SAMPLES)
    os.makedirs(os.path.join(OUT_DIR, "data"), exist_ok=True)
    with open(os.path.join(OUT_DIR, "data", "run_info.json"), "w") as fh:
        json.dump(info, fh, indent=1)
    done = []
    try:
        for n in todo:
            done.append(do_config(sc, V, cam, sun, n, cfgs[n]))
            with open(os.path.join(OUT_DIR, "data", "run_info_done.json"), "w") as fh:
                json.dump(done, fh, indent=1)
    finally:
        cleanup(restore)
    return dict(info, done=done)
