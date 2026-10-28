"""
brightness_map.py - how bright is each object for every combination of Sun direction and observer direction?

The project goal (Oisin, 19 Oct): tell what a satellite is doing from low-resolution, point-like images
taken from the ground.  The first step is to map the brightness an observer would measure for every
illumination angle (where the Sun is, seen from the satellite) and every observing angle (where the
observer is, seen from the satellite), under ideal conditions: no noise, no atmosphere, one Sun, black sky.
The plots made from this show the range of values and where different geometries give the same
brightness (the degeneracy).

WHAT IS MEASURED
  * Directions are N_DIRS points spread evenly over a sphere (a Fibonacci sphere), fixed to the object's
    body (+Z = model up, as in the other scripts).  Every Sun direction is paired with every observer
    direction: N x N geometries per object (48 -> 2304 geometries, neighbours about 30 degrees apart).
  * The camera is orthographic (parallel rays, as at orbital range).  Brightness = sum of all pixel
    luminance (32-bit linear EXR) x the area of one pixel in m^2, so objects of different size and framing
    can be compared.  This is the single-point brightness: the right-hand end of the washout graph.
  * Phase angle = angle between the Sun and observer directions (0 = Sun behind the observer).

OBJECTS
  A, C       Aqua (detailed, 115k triangles) and Suomi NPP (low-poly), taken from the open scene
  shapes     matte sphere, matte plate, shiny plate, matte cube, matte cylinder, matte box-wing
             (a cube with one flat solar wing, the simplest satellite-like shape)

  A 30-degree grid rarely lands on the very narrow glints of shiny surfaces (about 1.6 degrees wide), so the
  shiny plate and any shiny satellite parts are under-sampled: their peaks are mostly missed.

Runs in its own temporary scene; the satellite scene is left as it was.  Resumable: each finished Sun
direction is saved straight away, so stopping and re-running carries on where it left off.

Usage (Blender console, or TEST = "brightness_map" in run_tests.py):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\brightness_map.py", run_name="bmap")
  ns["run"]()                      # renders for about 10 minutes, then stops; call again until remaining == 0
  ns["run"](objects=["A", "C"])    # just the two satellites
  About 0.35 s per render: 2304 renders per object, so ~15 min per object, ~2 h for all eight.
Then, outside Blender:  python plots/plot_brightness_map.py
"""
import csv
import json
import math
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = r"C:\SSA\FYProject_SSA_Training"   # project root
OUT_DIR = os.path.join(ROOT, "brightness_map")
N_DIRS = 48                 # directions on the sphere; N x N geometries per object
RES = 256
SAMPLES = 16
SUN_STRENGTH = 4.0
SCENE = "SSA_BrightnessMap"

SATELLITES = {"A": dict(collection="Satellite_Detailed", root="Aqua_Detailed_root", label="Aqua (detailed, 115k)"),
              "C": dict(collection="Satellite_LowPoly", root="SuomiNPP_LowPoly_root", label="Suomi NPP (low-poly, 4k)")}
SHAPES = {"sphere_matte": "matte sphere", "plate_matte": "matte flat plate", "plate_shiny": "shiny flat plate",
          "cube_matte": "matte cube", "cylinder_matte": "matte cylinder", "boxwing_matte": "matte box-wing"}
OBJECTS = list(SATELLITES) + list(SHAPES)

PLATE = 2.0                                     # plate edge, m (same as material_tests.py)
SPHERE_R = math.sqrt(PLATE * PLATE / math.pi)   # same projected area as the plate seen face-on
SHINY_ROUGHNESS = 0.15

HEADER = ["object", "sun_i", "obs_i", "sun_x", "sun_y", "sun_z", "obs_x", "obs_y", "obs_z", "phase_deg",
          "brightness", "pixel_sum", "pixel_area_m2", "border_alpha"]


def fibonacci_directions(n):
    """n unit vectors spread almost evenly over the sphere."""
    k = np.arange(n) + 0.5
    z = 1.0 - 2.0 * k / n
    r = np.sqrt(1.0 - z * z)
    phi = k * math.pi * (3.0 - math.sqrt(5.0))
    return [Vector((float(r[i] * math.cos(phi[i])), float(r[i] * math.sin(phi[i])), float(z[i]))) for i in range(n)]


def look_along(obj, vec):
    """Orient obj so its -Z axis (camera / sun-light forward axis) points along vec."""
    obj.rotation_euler = vec.normalized().to_track_quat('-Z', 'Y').to_euler()


# ---------------------------------------------------------------------------------------
# scene construction
# ---------------------------------------------------------------------------------------
def _material(name, metallic, roughness):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:           # matte surfaces: no extra specular highlight
        bsdf.inputs["Specular IOR Level"].default_value = 0.0 if metallic == 0 else 0.5
    return m


def _shape_mesh(key):
    bm = bmesh.new()
    smooth = False
    if key == "sphere_matte":
        bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=SPHERE_R)
        smooth = True
    elif key in ("plate_matte", "plate_shiny"):
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=PLATE / 2)     # 2 x 2 m, normal +Z
    elif key == "cube_matte":
        bmesh.ops.create_cube(bm, size=1.6)
    elif key == "cylinder_matte":
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64, radius1=0.6, radius2=0.6, depth=2.2)
    elif key == "boxwing_matte":
        bmesh.ops.create_cube(bm, size=1.2)
        wing = bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=(1.5, 0.5, 1.0), verts=wing)                        # 3 x 1 m wing
        bmesh.ops.translate(bm, vec=(0.6 + 0.2 + 1.5, 0.0, 0.0), verts=wing)        # off the +X face
    else:
        raise ValueError(key)
    me = bpy.data.meshes.new("BM_" + key)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        # round surfaces shaded smooth; flat faces (plates, cube, cylinder caps) stay flat
        p.use_smooth = smooth or (key == "cylinder_matte" and abs(p.normal.z) < 0.5)
    return me


def _new_scene():
    if SCENE in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes[SCENE])
    sc = bpy.data.scenes.new(SCENE)
    cam = bpy.data.objects.new("BM_cam", bpy.data.cameras.new("BM_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    sun = bpy.data.objects.new("BM_sun", bpy.data.lights.new("BM_sun", 'SUN'))
    sc.collection.objects.link(sun)
    sun.data.energy = SUN_STRENGTH
    sun.data.angle = math.radians(0.53)

    w = bpy.data.worlds.get("BM_black") or bpy.data.worlds.new("BM_black")
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
    sc.view_settings.view_transform = 'Standard'      # keep pixel values linear and unstyled
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    r.image_settings.file_format = 'OPEN_EXR'
    r.image_settings.color_depth = '32'
    return sc, cam, sun


def _attach(sc, key):
    """Put one object into the scene.  Returns (collection, undo function)."""
    if key in SATELLITES:
        m = SATELLITES[key]
        col = bpy.data.collections[m["collection"]]
        pivot = bpy.data.objects.get(m["root"].replace("_root", "_pivot"))
        old_rot = tuple(pivot.rotation_euler) if pivot else None
        old_hide = col.hide_render
        if pivot:
            pivot.rotation_euler = (0, 0, 0)          # measure in the satellite's own (body) frame
        col.hide_render = False
        sc.collection.children.link(col)

        def undo():
            sc.collection.children.unlink(col)
            col.hide_render = old_hide
            if pivot:
                pivot.rotation_euler = old_rot
        return col, undo

    col = bpy.data.collections.new("BM_" + key)
    sc.collection.children.link(col)
    mat = _material("BM_mirror", 1.0, SHINY_ROUGHNESS) if key.endswith("_shiny") else _material("BM_matte", 0.0, 1.0)
    ob = bpy.data.objects.new("BM_" + key, _shape_mesh(key))
    ob.data.materials.append(mat)
    col.objects.link(ob)

    def undo():
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.collections.remove(col)
    return col, undo


def _bounds(col):
    """Centre and bounding-sphere radius of the visible meshes in a collection (world space)."""
    bpy.context.view_layer.update()
    meshes = [o for o in col.all_objects if o.type == 'MESH' and not o.hide_render]
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    tris = 0
    for o in meshes:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    return (mn + mx) / 2, (mx - mn).length / 2, tris


# ---------------------------------------------------------------------------------------
# measuring
# ---------------------------------------------------------------------------------------
def _render(sc, tmp):
    """Render; return (sum of linear pixel luminance, alpha on the picture border)."""
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
    return float(lum.astype(np.float64).sum()), edge


def _done_suns(path):
    """Sun directions already finished for one object (read from its CSV)."""
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    counts = {}
    for r in rows:
        counts[int(r["sun_i"])] = counts.get(int(r["sun_i"]), 0) + 1
    return {i for i, n in counts.items() if n > 0}


def _check_directions(data_dir, dirs):
    """Keep the direction list on disk; refuse to mix data made with a different N."""
    path = os.path.join(data_dir, "directions.json")
    if os.path.exists(path):
        with open(path) as fh:
            old = json.load(fh)
        if old["n"] != len(dirs):
            raise RuntimeError(f"{data_dir} holds data for N = {old['n']} directions, not {len(dirs)}. "
                               "Use the same N, or move the old data folder away first.")
        return
    with open(path, "w") as fh:
        json.dump(dict(n=len(dirs), dirs=[list(map(float, d)) for d in dirs]), fh, indent=1)


def run(objects=None, max_seconds=600, n_dirs=N_DIRS, out_dir=OUT_DIR):
    """Render whatever is still missing, stopping after about max_seconds.  Resumable."""
    t0 = time.perf_counter()
    objects = OBJECTS if objects is None else list(objects)
    unknown = [k for k in objects if k not in OBJECTS]
    if unknown:
        raise ValueError(f"unknown objects {unknown}; choose from {OBJECTS}")
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    dirs = fibonacci_directions(n_dirs)
    _check_directions(data_dir, dirs)
    info_path = os.path.join(data_dir, "objects.json")
    info = json.load(open(info_path)) if os.path.exists(info_path) else {}

    sc, cam, sun = _new_scene()
    tmp = os.path.join(data_dir, "_tmp")
    rendered = 0
    timed_out = False
    try:
        for key in objects:
            path = os.path.join(data_dir, f"map_{key}.csv")
            done = _done_suns(path)
            if len(done) >= n_dirs:
                continue
            if time.perf_counter() - t0 > max_seconds:
                timed_out = True
                break
            col, undo = _attach(sc, key)
            try:
                centre, radius, tris = _bounds(col)
                cam.data.ortho_scale = 2.0 * radius * 1.03
                dist = radius * 4.0 + 1.0
                cam.data.clip_start, cam.data.clip_end = 0.01, dist + radius * 2.0 + 10.0
                pix_area = (cam.data.ortho_scale / RES) ** 2
                info[key] = dict(label=SATELLITES[key]["label"] if key in SATELLITES else SHAPES[key],
                                 kind="satellite" if key in SATELLITES else "shape", triangles=tris,
                                 radius_m=round(radius, 3), ortho_scale_m=round(cam.data.ortho_scale, 3),
                                 res=RES, samples=SAMPLES)
                with open(info_path, "w") as fh:
                    json.dump(info, fh, indent=1)
                for i, s in enumerate(dirs):
                    if i in done:
                        continue
                    if time.perf_counter() - t0 > max_seconds:
                        timed_out = True
                        break
                    sun.location = centre + s * dist * 2
                    look_along(sun, -s)                                  # light travels towards the object
                    rows = []
                    for j, o in enumerate(dirs):
                        cam.location = centre + o * dist
                        look_along(cam, -o)
                        bpy.context.view_layer.update()
                        flux, edge = _render(sc, tmp)
                        rendered += 1
                        phase = math.degrees(math.acos(max(-1.0, min(1.0, s.dot(o)))))
                        rows.append([key, i, j, round(s.x, 5), round(s.y, 5), round(s.z, 5),
                                     round(o.x, 5), round(o.y, 5), round(o.z, 5), round(phase, 3),
                                     flux * pix_area, flux, pix_area, edge])
                    # every object is lit for some observers in every Sun direction, so an all-black set
                    # means the renderer has failed (seen once: the GPU driver gave black frames, then crashed)
                    if max(r[11] for r in rows) == 0.0:
                        raise RuntimeError(f"{key}: every render for Sun direction {i} came out black. The graphics "
                                           "driver has probably failed: restart Blender and run again (nothing was saved "
                                           "for this direction).")
                    new = not os.path.exists(path)
                    with open(path, "a", newline="") as fh:              # one Sun direction at a time
                        w = csv.writer(fh)
                        if new:
                            w.writerow(HEADER)
                        w.writerows(rows)
                    print(f"[brightness_map] {key}: Sun direction {i + 1}/{n_dirs} done "
                          f"({time.perf_counter() - t0:.0f} s)")
            finally:
                undo()
            if timed_out:
                break
    finally:
        bpy.data.scenes.remove(sc)
        for name in ("BM_cam", "BM_sun"):
            if name in bpy.data.objects:
                bpy.data.objects.remove(bpy.data.objects[name])

    remaining = {}
    for key in objects:
        left = n_dirs - len(_done_suns(os.path.join(data_dir, f"map_{key}.csv")))
        if left:
            remaining[key] = left
    return dict(rendered_this_call=rendered, seconds=round(time.perf_counter() - t0, 1),
                remaining_sun_directions=remaining, remaining=sum(remaining.values()),
                data=data_dir)
