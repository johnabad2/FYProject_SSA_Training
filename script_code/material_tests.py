"""
material_tests.py - how brightness depends on angle for three kinds of surface.

Objects (equal projected area, 4 m^2, when seen face-on):
  plate_diffuse  - flat 2 x 2 m plate, matte (Lambertian)
  sphere_diffuse - matte sphere, radius 1.128 m
  panel_shiny    - the same flat plate with a mirror-like metal surface

Experiment A  "spin":  each object spins about the vertical axis through 360 degrees while the
  Sun and the camera stay put (this is a satellite tumbling past an observer).
  Brightness = total linear light the camera receives from the object.
Experiment B  "distance": the matte sphere is moved away from a perspective camera, showing that
  only its apparent size (and so total brightness, ~1/d^2) changes.

GEOMETRY (all in the horizontal plane, +Z up)
  camera looks along +Y from -Y (azimuth -90 deg); the Sun is PHASE_DEG away from the camera
  direction, at azimuth -90 + PHASE_DEG.  At spin angle 0 the plate faces the camera.
  A flat mirror flashes when its normal bisects the Sun and camera directions:
  spin = PHASE/2 (front face) and PHASE/2 + 180 (back face).

Runs in its own temporary scene, so your satellite scene is not touched.
Usage (Blender console):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\material_tests.py", run_name="mt")
  ns["spin_sweep"]("plate_diffuse"); ns["spin_sweep"]("sphere_diffuse"); ns["spin_sweep"]("panel_shiny")
  ns["distance_sweep"]()
"""
import csv
import math
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

OUT_DIR = r"C:\SSA\FYProject_SSA_Training\material_tests"
PHASE_DEG = 60.0            # angle between the Sun and the camera as seen from the object
STEP_DEG = 2.0              # coarse spin step
RES = 256
SAMPLES = 16
SUN_STRENGTH = 4.0
SAMPLE_ANGLES = (0, 30, 60, 90, 120, 210)     # spin angles whose pictures are kept as PNG
PLATE = 2.0                                   # plate edge length, m
SPHERE_R = math.sqrt(PLATE * PLATE / math.pi)  # same projected area as the plate seen face-on
DISTANCES = (10, 14, 20, 28, 40, 57, 80)       # metres, for the distance sweep
SHINY_ROUGHNESS = 0.15      # polished but not a perfect mirror, so the glint has a realistic width

SCENE_NAME = "SSA_Materials"
OBJECTS = ("plate_diffuse", "sphere_diffuse", "panel_shiny")


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


def _plate_mesh(name):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=PLATE / 2)
    bm.transform(Matrix.Rotation(math.radians(90), 4, 'X'))      # face the camera (normal -Y)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _sphere_mesh(name):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=SPHERE_R)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _clean_old():
    if SCENE_NAME in bpy.data.scenes:
        bpy.data.scenes.remove(bpy.data.scenes[SCENE_NAME])
    for o in [o for o in bpy.data.objects if o.name.startswith("MT_")]:
        bpy.data.objects.remove(o)


def build_scene():
    _clean_old()
    sc = bpy.data.scenes.new(SCENE_NAME)
    col = sc.collection
    mats = {"matte": _material("MT_matte", 0.0, 1.0),
            "mirror": _material("MT_mirror", 1.0, SHINY_ROUGHNESS)}
    specs = {"plate_diffuse": (_plate_mesh("MT_plate_d"), mats["matte"]),
             "sphere_diffuse": (_sphere_mesh("MT_sphere"), mats["matte"]),
             "panel_shiny": (_plate_mesh("MT_plate_s"), mats["mirror"])}
    for key, (mesh, mat) in specs.items():
        ob = bpy.data.objects.new("MT_" + key, mesh)
        ob.data.materials.append(mat)
        col.objects.link(ob)

    cam_data = bpy.data.cameras.new("MT_cam")
    cam = bpy.data.objects.new("MT_cam", cam_data)
    col.objects.link(cam)
    sc.camera = cam

    sun_data = bpy.data.lights.new("MT_sun", 'SUN')
    sun_data.energy = SUN_STRENGTH
    sun_data.angle = math.radians(0.53)
    sun = bpy.data.objects.new("MT_sun", sun_data)
    col.objects.link(sun)
    toward_sun = Vector((math.cos(math.radians(-90 + PHASE_DEG)),
                         math.sin(math.radians(-90 + PHASE_DEG)), 0.0))
    sun.rotation_euler = (-toward_sun).to_track_quat('-Z', 'Y').to_euler()

    w = bpy.data.worlds.get("MT_black") or bpy.data.worlds.new("MT_black")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
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
    return sc


def _show_only(sc, key):
    for k in OBJECTS:
        bpy.data.objects["MT_" + k].hide_render = (k != key)
        bpy.data.objects["MT_" + k].hide_viewport = (k != key)


def _ortho_camera(sc):
    cam = sc.camera
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 4.6
    cam.data.clip_start, cam.data.clip_end = 0.1, 500
    cam.location = (0, -20, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)         # looks along +Y


def _persp_camera(sc, distance):
    cam = sc.camera
    cam.data.type = 'PERSP'
    cam.data.lens = 50
    cam.data.sensor_width = 36
    cam.data.clip_start, cam.data.clip_end = 0.1, 1000
    cam.location = (0, -distance, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)


# ---------------------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------------------
def _render_and_measure(sc, tmp_path, png_path=None):
    """Render, then return (total linear brightness, apparent area in pixels, render seconds)."""
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.filepath = tmp_path
    t0 = time.perf_counter()
    bpy.ops.render.render(scene=sc.name, write_still=True)
    secs = time.perf_counter() - t0
    if png_path:                                          # keep a viewable picture
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_depth = '8'
        bpy.data.images["Render Result"].save_render(png_path, scene=sc)
        sc.render.image_settings.file_format = 'OPEN_EXR'
        sc.render.image_settings.color_depth = '32'
    exr = tmp_path + ".exr"
    img = bpy.data.images.load(exr)
    img.colorspace_settings.name = 'Non-Color'
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    os.remove(exr)
    px = px.reshape(-1, 4)
    lum = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
    return float(lum.sum()), float(px[:, 3].sum()), secs


def _angles(key):
    coarse = [a * STEP_DEG for a in range(int(360 / STEP_DEG))]
    if key != "panel_shiny":
        return sorted(coarse)
    # a mirror flashes only over a fraction of a degree of spin, so sample very finely there:
    # 0.1 deg steps within +-3 deg and 0.5 deg steps within +-12 deg of each predicted flash
    extra = []
    for centre in (PHASE_DEG / 2, PHASE_DEG / 2 + 180):
        extra += [centre + k * 0.5 for k in range(-24, 25)]
        extra += [centre + k * 0.1 for k in range(-30, 31)]
    allv = {round(a % 360, 4) for a in coarse + extra}
    return sorted(allv)


def spin_sweep(key):
    """Spin one object through 360 degrees; write material_tests/data/spin_<key>.csv."""
    assert key in OBJECTS, key
    os.makedirs(os.path.join(OUT_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "samples"), exist_ok=True)
    sc = build_scene()
    _show_only(sc, key)
    _ortho_camera(sc)
    ob = bpy.data.objects["MT_" + key]
    tmp = os.path.join(OUT_DIR, "data", "_tmp_" + key)
    rows = []
    t0 = time.perf_counter()
    try:
        for ang in _angles(key):
            ob.rotation_euler = (0, 0, math.radians(ang))
            bpy.context.view_layer.update()
            png = None
            if any(abs(ang - s) < 1e-6 for s in SAMPLE_ANGLES):
                png = os.path.join(OUT_DIR, "samples", f"{key}_{int(round(ang)):03d}.png")
            flux, area, secs = _render_and_measure(sc, tmp, png)
            rows.append((key, round(ang, 4), flux, area))
    finally:
        bpy.data.scenes.remove(sc)
    path = os.path.join(OUT_DIR, "data", f"spin_{key}.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["object", "spin_deg", "brightness", "apparent_area_px"])
        w.writerows(rows)
    return dict(object=key, frames=len(rows), seconds=round(time.perf_counter() - t0, 1), csv=path,
                max_brightness=max(r[2] for r in rows))


def distance_sweep():
    """Matte sphere at increasing distance from a perspective camera."""
    os.makedirs(os.path.join(OUT_DIR, "data"), exist_ok=True)
    sc = build_scene()
    _show_only(sc, "sphere_diffuse")
    tmp = os.path.join(OUT_DIR, "data", "_tmp_dist")
    rows = []
    try:
        for d in DISTANCES:
            _persp_camera(sc, d)
            bpy.context.view_layer.update()
            flux, area, _ = _render_and_measure(sc, tmp)
            rows.append(("sphere_diffuse", d, flux, area))
    finally:
        bpy.data.scenes.remove(sc)
    path = os.path.join(OUT_DIR, "data", "distance_sphere_diffuse.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["object", "distance_m", "brightness", "apparent_area_px"])
        w.writerows(rows)
    return dict(csv=path, rows=len(rows))
