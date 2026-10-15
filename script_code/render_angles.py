"""
render_angles.py - render the satellite models under different Sun angles,
viewing angles and satellite rotations.

Run it any of these ways:
  * Blender > Scripting tab > open this file > Run Script
  * Command line (no UI):
      blender -b satellite_comparison.blend -P render_angles.py -- --engine EEVEE --out C:\\SSA\\renders
  * From Python:  ns = runpy.run_path(path, run_name="render_angles"); ns["main"](...)

ANGLE CONVENTIONS (all in degrees)
  sun_az / cam_az : azimuth, measured counter-clockwise (seen from above, +Z up)
                    starting at the +X axis. 0 = +X, 90 = +Y, 180 = -X, 270 = -Y.
  sun_el / cam_el : elevation above the horizontal XY plane. 90 = straight above.
  rot_x / rot_z   : rotation of the satellite about its own centre (X then Z).
  The Sun / camera sit on a sphere around the satellite, so
  sun_az == cam_az and sun_el == cam_el means "Sun directly behind the camera"
  (the satellite is fully lit from the camera's point of view).

Outputs: one PNG per model per shot, plus render_log.csv with triangle counts
and render times (handy for the detailed vs low-poly comparison).
"""
import bpy
import csv
import math
import os
import sys
import time
from mathutils import Vector

# --------------------------------------------------------------------------
# CONFIG - edit these
# --------------------------------------------------------------------------
# collection / root-empty names created when the models were imported
MODELS = [
    dict(label="Aqua_detailed",    collection="Satellite_Detailed", root="Aqua_Detailed_root"),
    dict(label="SuomiNPP_lowpoly", collection="Satellite_LowPoly",  root="SuomiNPP_LowPoly_root"),
]

# A handful of shots. Add, remove or edit freely.
SHOTS = [
    dict(name="fully_lit",     sun_az=45,  sun_el=35, cam_az=45,  cam_el=20, rot_x=0, rot_z=0),
    dict(name="side_view",     sun_az=45,  sun_el=35, cam_az=135, cam_el=20, rot_x=0, rot_z=0),
    dict(name="rear_view",     sun_az=45,  sun_el=35, cam_az=225, cam_el=20, rot_x=0, rot_z=0),
    dict(name="rotated_90",    sun_az=45,  sun_el=35, cam_az=45,  cam_el=20, rot_x=0, rot_z=90),
    dict(name="grazing_sun",   sun_az=180, sun_el=8,  cam_az=45,  cam_el=20, rot_x=0, rot_z=0),
    dict(name="backlit",       sun_az=225, sun_el=15, cam_az=45,  cam_el=15, rot_x=0, rot_z=0),
]

SUN_STRENGTH = 4.0        # W/m^2 in Blender's units; 3-5 looks right with AgX/Filmic
SUN_ANGLE_DEG = 0.53      # angular size of the real Sun seen from Earth orbit
AMBIENT = 0.02            # faint fill ("Earthshine"); 0 = pitch-black shadows (realistic but harsh)
FRAMING = 1.0             # camera distance as a fraction of "just fits the bounding sphere"; <1 = tighter, may clip
RES = (1280, 720)
SAMPLES = 64


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def direction(az_deg, el_deg):
    """Unit vector for an azimuth/elevation pair (see conventions above)."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))


def look_along(obj, vec):
    """Orient obj so its -Z axis (camera / sun-light forward axis) points along vec."""
    obj.rotation_euler = vec.normalized().to_track_quat('-Z', 'Y').to_euler()


def world_bbox(meshes):
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def triangle_count(meshes):
    total = 0
    for o in meshes:
        o.data.calc_loop_triangles()
        total += len(o.data.loop_triangles)
    return total


def pick_engine(name):
    """Return the engine identifier that this Blender version accepts for 'EEVEE' / 'CYCLES'.

    Tries assigning each candidate instead of reading the engine enum, because the enum
    listing can leave out engines that come from add-ons (Cycles).
    """
    scene = bpy.context.scene
    original = scene.render.engine
    wanted = {'EEVEE': ['BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'], 'CYCLES': ['CYCLES']}[name.upper()]
    for cand in wanted:
        try:
            scene.render.engine = cand
            scene.render.engine = original
            return cand
        except (TypeError, ValueError):
            continue
    scene.render.engine = original
    raise RuntimeError(f"Render engine {name!r} is not available in this Blender "
                       "(for Cycles: Edit > Preferences > Add-ons > enable 'Cycles Render Engine').")


def setup_group(model):
    """Find the satellite, and give it a pivot empty at its centre so it rotates in place."""
    col = bpy.data.collections[model["collection"]]
    meshes = [o for o in col.all_objects if o.type == 'MESH']
    root = bpy.data.objects[model["root"]]
    pivot_name = model["root"].replace("_root", "_pivot")
    pivot = bpy.data.objects.get(pivot_name)
    if pivot is not None:
        pivot.rotation_euler = (0, 0, 0)          # measure the un-rotated model
    bpy.context.view_layer.update()
    mn, mx = world_bbox(meshes)
    radius = (mx - mn).length / 2
    centre = (mn + mx) / 2
    if pivot is None:
        pivot = bpy.data.objects.new(pivot_name, None)
        col.objects.link(pivot)
        pivot.location = centre
        bpy.context.view_layer.update()
        root.parent = pivot
        root.matrix_parent_inverse = pivot.matrix_world.inverted()
        bpy.context.view_layer.update()
    elif (pivot.matrix_world.translation - centre).length > 1e-4:
        # pivot has drifted away from the model's centre (e.g. the model was moved):
        # re-centre it without moving the model, so rotation and framing stay correct
        world = root.matrix_world.copy()
        pivot.location = centre
        bpy.context.view_layer.update()
        root.matrix_world = world
        bpy.context.view_layer.update()
    return dict(model=model, col=col, meshes=meshes, pivot=pivot, radius=radius,
                tris=triangle_count(meshes))


def ensure_sun():
    obj = bpy.data.objects.get("RenderSun")
    if obj is None:
        data = bpy.data.lights.new("RenderSun", 'SUN')
        obj = bpy.data.objects.new("RenderSun", data)
        bpy.context.scene.collection.objects.link(obj)
    obj.data.energy = SUN_STRENGTH
    obj.data.angle = math.radians(SUN_ANGLE_DEG)
    return obj


def ensure_camera():
    obj = bpy.data.objects.get("RenderCam")
    if obj is None:
        data = bpy.data.cameras.new("RenderCam")
        obj = bpy.data.objects.new("RenderCam", data)
        bpy.context.scene.collection.objects.link(obj)
    obj.data.lens = 50
    obj.data.clip_start = 0.1
    obj.data.clip_end = 5000
    return obj


def ensure_space_world(ambient=None):
    w = bpy.data.worlds.get("SSA_Space")
    if w is None:
        w = bpy.data.worlds.new("SSA_Space")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.5, 0.6, 1.0, 1.0)     # faint cool "Earthshine" tint
    bg.inputs["Strength"].default_value = AMBIENT if ambient is None else ambient                # 0 = pure black background/shadows
    return w


def configure_render(scene, engine, res, samples):
    scene.render.engine = pick_engine(engine)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    try:
        if scene.render.engine == 'CYCLES':
            scene.cycles.samples = samples
            scene.cycles.use_denoising = True
        else:
            scene.eevee.taa_render_samples = samples
    except Exception as exc:  # property names shift between Blender versions
        print("Could not set samples:", exc)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(out_dir=None, engine="EEVEE", shots=None, models=None, res=RES, samples=SAMPLES,
         framing=None, filename=None, write_log=True, ambient=None):
    """filename(model_label, index, shot) -> str lets a caller choose output names (used for
    animation frames); write_log=False skips render_log.csv.
    ambient overrides AMBIENT (0 = pure black space, no fill light)."""
    scene = bpy.context.scene
    shots = SHOTS if shots is None else shots
    models = MODELS if models is None else models
    if out_dir is None:
        out_dir = bpy.path.abspath("//renders") if bpy.data.filepath else os.path.join(
            os.path.expanduser("~"), "ssa_renders")
    os.makedirs(out_dir, exist_ok=True)

    groups = [setup_group(m) for m in models]
    sun, cam, world = ensure_sun(), ensure_camera(), ensure_space_world(ambient)

    # remember everything we change so the scene is left as we found it
    saved = dict(camera=scene.camera, world=scene.world, engine=scene.render.engine,
                 res=(scene.render.resolution_x, scene.render.resolution_y),
                 path=scene.render.filepath,
                 # every satellite collection (not just the ones in this call) so the others can be hidden
                 col_hide={m["collection"]: bpy.data.collections[m["collection"]].hide_render
                           for m in MODELS if m["collection"] in bpy.data.collections},
                 other_lights={o.name: o.hide_render for o in bpy.data.objects
                               if o.type == 'LIGHT' and o is not sun},
                 pivot_rot={g["pivot"].name: tuple(g["pivot"].rotation_euler) for g in groups})
    log_rows = []
    try:
        configure_render(scene, engine, res, samples)
        scene.camera = cam
        scene.world = world
        for name in saved["other_lights"]:
            bpy.data.objects[name].hide_render = True       # only the Sun lights the scene

        for g in groups:
            for name in saved["col_hide"]:                  # show only the model being rendered,
                bpy.data.collections[name].hide_render = (name != g["col"].name)   # even if it is rendered alone
            centre = g["pivot"].matrix_world.translation.copy()
            # true limiting field of view for this picture shape (the camera's own angle_y
            # uses the sensor height and overestimates it for 16:9 renders)
            rx, ry = res
            half_long = math.tan(cam.data.angle_x / 2)   # sensor fit AUTO: 36 mm spans the longer side
            fov = 2 * math.atan(half_long * min(rx, ry) / max(rx, ry))
            fit = FRAMING if framing is None else framing
            dist = g["radius"] * fit / math.sin(fov / 2)        # fit < 1 = tighter (may clip); 1 = never clips

            for i, shot in enumerate(shots, 1):
                g["pivot"].rotation_euler = (math.radians(shot.get("rot_x", 0)), 0,
                                             math.radians(shot.get("rot_z", 0)))
                sun_dir = direction(shot["sun_az"], shot["sun_el"])      # centre -> Sun
                sun.location = centre + sun_dir * (dist * 2)
                look_along(sun, -sun_dir)                                 # light travels towards the satellite
                cam_dir = direction(shot["cam_az"], shot["cam_el"])
                cam.location = centre + cam_dir * dist
                look_along(cam, centre - cam.location)
                bpy.context.view_layer.update()

                fname = (filename(g['model']['label'], i, shot) if filename
                         else f"{g['model']['label']}_{i:02d}_{shot['name']}.png")
                scene.render.filepath = os.path.join(out_dir, fname)
                t0 = time.perf_counter()
                bpy.ops.render.render(write_still=True)
                secs = time.perf_counter() - t0
                print(f"[render] {fname}  {secs:.1f}s")
                log_rows.append([g["model"]["label"], g["tris"], shot["name"], shot["sun_az"],
                                 shot["sun_el"], shot["cam_az"], shot["cam_el"],
                                 shot.get("rot_x", 0), shot.get("rot_z", 0),
                                 scene.render.engine, f"{res[0]}x{res[1]}", samples,
                                 round(secs, 2), fname])
    finally:
        # put everything back
        scene.camera, scene.world = saved["camera"], saved["world"]
        scene.render.engine = saved["engine"]
        scene.render.resolution_x, scene.render.resolution_y = saved["res"]
        scene.render.filepath = saved["path"]
        for name, hide in saved["col_hide"].items():
            bpy.data.collections[name].hide_render = hide
        for name, hide in saved["other_lights"].items():
            bpy.data.objects[name].hide_render = hide
        for name, rot in saved["pivot_rot"].items():
            bpy.data.objects[name].rotation_euler = rot

    if write_log:
        log_path = os.path.join(out_dir, "render_log.csv")
        new = not os.path.exists(log_path)
        with open(log_path, "a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["model", "triangles", "shot", "sun_az", "sun_el", "cam_az", "cam_el",
                            "rot_x", "rot_z", "engine", "resolution", "samples", "seconds", "file"])
            w.writerows(log_rows)
    return dict(out_dir=out_dir, renders=len(log_rows),
                seconds=[(r[0], r[2], r[12]) for r in log_rows])


if __name__ == "__main__":
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None)
    p.add_argument("--engine", default="EEVEE", choices=["EEVEE", "CYCLES"])
    p.add_argument("--samples", type=int, default=SAMPLES)
    a = p.parse_args(argv)
    print(main(out_dir=a.out, engine=a.engine, samples=a.samples))
