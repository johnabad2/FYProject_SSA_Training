"""
setup_scene.py - put the open Blender scene into the state the SSA tests expect.

  * pure black "space" world (no ambient light)
  * one Sun lamp (RenderSun) with the Sun's real angular size, strength 4
  * one camera (RenderCam) framed on Aqua, set as the active camera
  * Aqua at the origin, Suomi NPP 50 units away, so the two satellites do not overlap
  * EEVEE, 1280 x 720, 64 samples; the 3D view shows the camera view in Rendered mode
  * any other lights are switched off (hidden, not deleted)

Safe to run again at any time.
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\setup_scene.py", run_name="setup"); ns["setup"]()
"""
import math
import os
import runpy

import bpy

HERE = r"C:\SSA\FYProject_SSA_Training"
SUN_AZ, SUN_EL = 45, 35        # Sun direction seen from the satellite
CAM_AZ, CAM_EL = 45, 20        # camera direction seen from the satellite
RES = (1280, 720)
SAMPLES = 64
LAYOUT = {"Aqua_Detailed_pivot": (0, 0, 0), "SuomiNPP_LowPoly_pivot": (0, -50, 0)}


def setup(frame_model=0, look_through_camera=True):
    sc = bpy.context.scene
    ra = runpy.run_path(os.path.join(HERE, "render_angles.py"), run_name="render_angles")

    for name, loc in LAYOUT.items():
        if name in bpy.data.objects:
            bpy.data.objects[name].location = loc
    bpy.context.view_layer.update()

    ra["AMBIENT"] = 0.0
    world = ra["ensure_space_world"]()
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.world = world

    sun, cam = ra["ensure_sun"](), ra["ensure_camera"]()
    for o in bpy.data.objects:                       # only the Sun lights the scene
        if o.type == 'LIGHT' and o is not sun:
            o.hide_render = o.hide_viewport = True

    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = SAMPLES
    sc.render.film_transparent = False

    g = ra["setup_group"](ra["MODELS"][frame_model])
    rx, ry = RES
    fov = 2 * math.atan(math.tan(cam.data.angle_x / 2) * min(rx, ry) / max(rx, ry))
    dist = g["radius"] * 1.05 / math.sin(fov / 2)
    centre = g["pivot"].matrix_world.translation.copy()
    sd, cd = ra["direction"](SUN_AZ, SUN_EL), ra["direction"](CAM_AZ, CAM_EL)
    sun.location = centre + sd * dist * 2
    ra["look_along"](sun, -sd)
    cam.location = centre + cd * dist
    ra["look_along"](cam, centre - cam.location)
    sc.camera = cam

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].shading.type = 'RENDERED'
            if look_through_camera:
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
    return dict(model=ra["MODELS"][frame_model]["label"], camera_distance=round(dist, 1))


if __name__ == "__main__":
    print(setup())
