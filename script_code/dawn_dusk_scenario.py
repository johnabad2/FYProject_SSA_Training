"""
dawn_dusk_scenario.py - render a satellite on a dawn-dusk (terminator) polar orbit, spinning,
as seen by a ground observer at twilight.

It builds on render_angles.py (same folder): this script works out plausible Sun and
observer directions for every moment of one visible pass, then hands them to render_angles.main().

Run it:
  * Blender console / Scripting tab:
        import runpy
        ns = runpy.run_path(r"C:\\SSA\\FYProject_SSA_Training\\script_code\\dawn_dusk_scenario.py", run_name="scenario")
        ns["run"]()                       # EEVEE, both satellites
        ns["run"](engine="CYCLES")        # slower, higher quality
  * Terminal:
        blender -b satellite_comparison.blend -P dawn_dusk_scenario.py -- --engine EEVEE

THE SCENARIO (simplified, not real orbit data)
  * Circular, sun-synchronous orbit at 705 km (Aqua's altitude), inclined ~98 deg, so it passes
    over the poles.  "Dawn-dusk" means the orbit plane is almost perpendicular to the Sun
    direction (beta angle ~85 deg): the satellite rides the day/night line and is sunlit all
    year, with the Sun low on its local horizon.
  * A ground observer sits slightly on the night side of the ground track, where the Sun is a few
    degrees below the horizon (twilight).  The sky is dark but the satellite is still in sunlight,
    which is the classic "bright satellite in the dusk sky" view.
  * The satellite spins about its own vertical (model Z) axis at a constant rate.
  * Earth rotation, atmosphere, Earth's shadow and the observer's real latitude are ignored.

LOCAL FRAME USED FOR THE ANGLES  (matches render_angles.py's az/el convention)
  +X = direction of flight, +Y = orbit normal (towards the Sun side), +Z = away from Earth.
  Azimuth is measured counter-clockwise from +X, elevation above the XY plane.
  So an observer on the ground appears at a NEGATIVE elevation (below the satellite).

ASSUMPTION about the models: model +Z is "up/zenith" and the satellite spins about it.
"""
import csv
import math
import os
import sys
import runpy

# ---------------------------------------------------------------------------
# scenario parameters - edit these
# ---------------------------------------------------------------------------
ALTITUDE_KM = 705.0         # Aqua's altitude (Suomi NPP is ~824 km)
BETA_DEG = 85.0             # angle between the Sun and the orbit plane; 90 = exactly dawn-dusk
OBSERVER_SUN_EL_DEG = -4.0  # Sun's elevation at the observer; -4 = just after sunset (twilight)
MIN_ELEVATION_DEG = 10.0    # satellite must be this high above the observer's horizon to be seen
SPIN_DEG_PER_S = 0.8        # satellite spin rate; 0.8 deg/s = one turn every 7.5 minutes
N_FRAMES = 10               # renders per satellite over the visible pass

R_EARTH = 6371.0            # km
MU = 398600.4418            # km^3/s^2


def _vec_sub(a, b): return tuple(x - y for x, y in zip(a, b))
def _dot(a, b): return sum(x * y for x, y in zip(a, b))
def _norm(a): return math.sqrt(_dot(a, a))


def compute_pass(n_frames=None):
    """Return (list of per-frame geometry dicts, metadata dict) for n_frames points along the pass."""
    n_frames = N_FRAMES if n_frames is None else n_frames
    r = R_EARTH + ALTITUDE_KM
    period = 2 * math.pi * math.sqrt(r ** 3 / MU)            # seconds
    rate = 360.0 / period                                     # orbital deg per second
    beta = math.radians(BETA_DEG)
    # sun direction in the orbit-fixed frame (x = orbit normal, y = towards closest approach)
    sun = (math.sin(beta), math.cos(beta), 0.0)
    # observer sits on the night side so the Sun is at OBSERVER_SUN_EL_DEG there:
    # cos(beta - delta) = sin(sun_el)  ->  delta = beta - 90 + sun_el
    delta = math.radians(BETA_DEG - 90.0 + OBSERVER_SUN_EL_DEG)
    obs = (R_EARTH * math.sin(delta), R_EARTH * math.cos(delta), 0.0)
    obs_up = tuple(c / R_EARTH for c in obs)

    samples = []
    g = -45.0
    while g <= 45.0:                                          # orbital phase, deg from closest approach
        gr = math.radians(g)
        pos = (0.0, r * math.cos(gr), r * math.sin(gr))
        to_sat = _vec_sub(pos, obs)
        rng = _norm(to_sat)
        elev = math.degrees(math.asin(_dot(to_sat, obs_up) / rng))
        if elev >= MIN_ELEVATION_DEG:
            samples.append((g, elev, rng))
        g += 0.05
    if len(samples) < 2:
        raise RuntimeError("No visible pass with these settings - lower MIN_ELEVATION_DEG or move the observer.")

    g_start, g_end = samples[0][0], samples[-1][0]
    frames = []
    for i in range(n_frames):
        g = g_start + (g_end - g_start) * i / (n_frames - 1)
        gr = math.radians(g)
        pos = (0.0, r * math.cos(gr), r * math.sin(gr))
        # local axes at the satellite: forward v, normal c (= +x), up u
        v = (0.0, -math.sin(gr), math.cos(gr))
        c = (1.0, 0.0, 0.0)
        u = (0.0, math.cos(gr), math.sin(gr))
        to_obs = _vec_sub(obs, pos)
        rng = _norm(to_obs)
        elev = math.degrees(math.asin(_dot(_vec_sub(pos, obs), obs_up) / rng))

        def to_az_el(vec):
            local = (_dot(vec, v), _dot(vec, c), _dot(vec, u))
            n = _norm(local)
            return (math.degrees(math.atan2(local[1], local[0])) % 360.0,
                    math.degrees(math.asin(local[2] / n)))

        sun_az, sun_el = to_az_el(sun)
        cam_az, cam_el = to_az_el(to_obs)
        t = (g - g_start) / rate                              # seconds since the pass began
        # phase angle = angle Sun-satellite-observer (0 = Sun behind the observer, 180 = backlit)
        phase = math.degrees(math.acos(max(-1.0, min(1.0, _dot(sun, to_obs) / rng))))
        frames.append(dict(i=i + 1, t=t, orbit_deg=g, obs_elev=elev, range_km=rng, phase=phase,
                           sun_az=sun_az, sun_el=sun_el, cam_az=cam_az, cam_el=cam_el,
                           spin=(SPIN_DEG_PER_S * t) % 360.0))
    meta = dict(period_min=period / 60, pass_seconds=(g_end - g_start) / rate,
                max_elev=max(s[1] for s in samples), observer_offset_km=abs(R_EARTH * delta),
                spin_turns=SPIN_DEG_PER_S * (g_end - g_start) / rate / 360.0)
    return frames, meta


def run(out_dir=None, engine="EEVEE", samples=64, res=(1280, 720), models=None, framing=1.05):
    here = os.path.dirname(os.path.abspath(globals().get("__file__", "")))
    if not here or not os.path.exists(os.path.join(here, "render_angles.py")):
        here = r"C:\SSA\FYProject_SSA_Training\script_code"
    ra = runpy.run_path(os.path.join(here, "render_angles.py"), run_name="render_angles")
    out_dir = out_dir or os.path.join(r"C:\SSA\FYProject_SSA_Training", "renders", "renders_dawn_dusk")

    frames, meta = compute_pass()
    shots = [dict(name=f"t{int(f['t']):03d}s_elev{int(round(f['obs_elev'])):02d}",
                  sun_az=f["sun_az"], sun_el=f["sun_el"], cam_az=f["cam_az"], cam_el=f["cam_el"],
                  rot_x=0, rot_z=f["spin"]) for f in frames]
    result = ra["main"](out_dir=out_dir, engine=engine, shots=shots, models=models,
                        res=res, samples=samples, framing=framing)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dawn_dusk_geometry.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "seconds", "observer_elev_deg", "range_km", "phase_angle_deg",
                    "sun_az", "sun_el", "cam_az", "cam_el", "spin_deg"])
        for f in frames:
            w.writerow([f["i"], round(f["t"], 1), round(f["obs_elev"], 1), round(f["range_km"]),
                        round(f["phase"], 1), round(f["sun_az"], 1), round(f["sun_el"], 1),
                        round(f["cam_az"], 1), round(f["cam_el"], 1), round(f["spin"], 1)])
    return dict(result, scenario=meta,
                frames=[(f["i"], round(f["t"]), round(f["obs_elev"]), round(f["phase"]),
                         round(f["spin"])) for f in frames])


if __name__ == "__main__":
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None)
    p.add_argument("--engine", default="EEVEE", choices=["EEVEE", "CYCLES"])
    p.add_argument("--samples", type=int, default=64)
    a = p.parse_args(argv)
    print(run(out_dir=a.out, engine=a.engine, samples=a.samples))
