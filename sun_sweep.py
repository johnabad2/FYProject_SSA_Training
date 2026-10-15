"""
sun_sweep.py - fixed satellite, fixed camera, a Sun that travels round the satellite on an ellipse.

The Sun starts directly ABOVE the satellite, swings down one side, passes UNDER it, and comes back up the
other side to the top.  Nothing else moves: the satellite does not spin and the camera does not move, so
every change in the pictures is due to the lighting alone.

THE PATH (all directions are seen from the satellite; +Z is up)
  The Sun sits on an ellipse in a vertical plane:
      position(t) = A * sin(t) * h  +  B * cos(t) * z          t = 0 ... 360 deg
  with h a horizontal axis, z straight up, A the horizontal and B the vertical radius of the ellipse.
  t = 0 is straight overhead, t = 90 is level on the h side, t = 180 is straight underneath, t = 270 is
  level on the other side.  A > B stretches the ellipse sideways, so the Sun moves faster over the top and
  bottom than near the horizon.  Only the Sun's direction matters for lighting (it is very far away).
  The plane is turned ELLIPSE_AZ_OFFSET degrees away from the camera direction so the Sun passes in front
  of the satellite on one side and behind it on the other.

Run (Blender console / Scripting tab):
  ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\sun_sweep.py", run_name="sweep")
  ns["run"]()                 # both satellites, 36 positions each (every 10 degrees along the ellipse)
Builds on render_angles.py (same folder).
"""
import csv
import math
import os
import runpy

from mathutils import Vector

HERE = r"C:\SSA\FYProject_SSA_Training"

CAM_AZ, CAM_EL = 45.0, 10.0         # fixed camera direction as seen from the satellite
ELLIPSE_AZ_OFFSET = 60.0            # horizontal axis of the ellipse, degrees away from the camera azimuth
A, B = 1.6, 1.0                     # horizontal and vertical radii of the ellipse (only their ratio matters)
STEP_DEG = 10                       # step along the ellipse (360 / STEP = number of pictures)
RES = (1280, 720)
SAMPLES = 64
AMBIENT = 0.0                       # 0 = pure black space: surfaces facing away from the Sun are completely dark


def sun_path(step=STEP_DEG):
    """List of dicts: ellipse angle t, Sun azimuth/elevation (render_angles convention), phase angle."""
    az_h = math.radians(CAM_AZ + ELLIPSE_AZ_OFFSET)
    h = Vector((math.cos(az_h), math.sin(az_h), 0.0))
    z = Vector((0.0, 0.0, 1.0))
    cam = Vector((math.cos(math.radians(CAM_EL)) * math.cos(math.radians(CAM_AZ)),
                  math.cos(math.radians(CAM_EL)) * math.sin(math.radians(CAM_AZ)),
                  math.sin(math.radians(CAM_EL))))
    out = []
    for i in range(int(round(360 / step))):
        t = i * step
        p = A * math.sin(math.radians(t)) * h + B * math.cos(math.radians(t)) * z
        d = p.normalized()
        out.append(dict(i=i + 1, t=t,
                        sun_az=math.degrees(math.atan2(d.y, d.x)) % 360.0,
                        sun_el=math.degrees(math.asin(max(-1.0, min(1.0, d.z)))),
                        phase=math.degrees(math.acos(max(-1.0, min(1.0, d.dot(cam)))))))
    return out


def run(out_dir=None, engine="EEVEE", samples=SAMPLES, res=RES, models=None, framing=1.05, ambient=AMBIENT):
    ra = runpy.run_path(os.path.join(HERE, "render_angles.py"), run_name="render_angles")
    out_dir = out_dir or os.path.join(HERE, "renders_sun_sweep")
    path = sun_path()
    shots = [dict(name=f"sun{int(p['t']):03d}", sun_az=p["sun_az"], sun_el=p["sun_el"],
                  cam_az=CAM_AZ, cam_el=CAM_EL, rot_x=0, rot_z=0) for p in path]
    result = ra["main"](out_dir=out_dir, engine=engine, shots=shots, models=models, res=res,
                        samples=samples, framing=framing, write_log=False, ambient=ambient,
                        filename=lambda lbl, i, shot: f"{lbl}_{shot['name']}.png")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "sun_path.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "ellipse_deg", "sun_az", "sun_el", "phase_deg"])
        for p in path:
            w.writerow([p["i"], p["t"], round(p["sun_az"], 2), round(p["sun_el"], 2), round(p["phase"], 2)])
    return dict(result, frames=len(path))


if __name__ == "__main__":
    print(run())
