"""
check_real_pass.py - independent checks of a real_pass.py run, saved so the numbers can be traced.

  python script_code/check_real_pass.py real_passes/AQUA_27424

Writes  <folder>/checks.json
  shadow     Skyfield's is_sunlit against a cylinder-shaped Earth shadow (in shadow if on the night side and
             less than one Earth radius from the Earth-Sun line), on every sample
  distance   the full calculation against the spherical-Earth slant-range formula
             d = sqrt((R+h)^2 - (R cos e)^2) - R sin e, using each sample's own height
  orbit      period, semi-major axis and height worked out by hand from the TLE (Kepler's third law), and the
             first-order J2 drift of the orbit plane against the sun-synchronous rate
See docs/REAL_PASSES_EXPLAINED.md for the physics and sources.
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

import numpy as np
from skyfield.api import EarthSatellite, Loader

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R_MEAN, R_EQ = 6371.0, 6378.137            # km, NASA Earth fact sheet
GM, J2 = 398600.4418, 1082.63e-6           # km^3/s^2; J2 from NASA Earth fact sheet
SUN_RATE = 360.0 / 365.2422                # deg/day, the Sun's apparent motion


def check(folder):
    info = json.load(open(os.path.join(folder, "run_info.json")))
    rows = list(csv.DictReader(open(os.path.join(folder, "samples.csv"))))
    load = Loader(os.path.join(ROOT, "real_passes", "ephemeris"), verbose=False)
    ts = load.timescale(); eph = load(info["ephemeris"])
    l1, l2 = info["tle"]
    sat = EarthSatellite(l1, l2, info["satellite"], ts)
    t = ts.from_datetimes([dt.datetime.fromisoformat(r["time_utc"].replace("Z", "+00:00")) for r in rows])

    # shadow
    r = sat.at(t).position.km
    s = (eph["sun"] - eph["earth"]).at(t).position.km
    shat = s / np.linalg.norm(s, axis=0)
    along = np.sum(r * shat, axis=0)
    perp = np.linalg.norm(r - along * shat, axis=0)
    lit_cyl = (along > 0) | (perp > R_MEAN)
    lit_sf = np.array([r_["sunlit"] == "1" for r_ in rows])
    bad = lit_cyl != lit_sf
    shadow = dict(samples=len(rows), agree_pct=round(100 * float(np.mean(~bad)), 2), disagree=int(bad.sum()),
                  max_km_from_shadow_edge_where_disagree=round(float(np.max(np.abs(perp[bad] - R_MEAN))), 1) if bad.any() else 0.0)

    # distance
    e = np.radians([float(x["elev_deg"]) for x in rows])
    h = np.array([float(x["height_km"]) for x in rows])
    rng = np.array([float(x["range_km"]) for x in rows])
    f = np.sqrt((R_MEAN + h) ** 2 - (R_MEAN * np.cos(e)) ** 2) - R_MEAN * np.sin(e)
    distance = dict(median_abs_diff_km=round(float(np.median(np.abs(f - rng))), 2),
                    max_abs_diff_km=round(float(np.max(np.abs(f - rng))), 2),
                    min_range_km=round(float(rng.min()), 1), max_range_km=round(float(rng.max()), 1))

    # orbit by hand from the TLE
    inc, ecc, n = float(l2[8:16]), float("0." + l2[26:33]), float(l2[52:63])
    T = 86400.0 / n
    w = 2 * math.pi / T
    a = (GM / w ** 2) ** (1 / 3)
    drift = math.degrees(-1.5 * w * J2 * (R_EQ / a) ** 2 * math.cos(math.radians(inc)) / (1 - ecc ** 2) ** 2) * 86400
    h_mean = a - R_MEAN
    lam = math.degrees(math.acos(R_MEAN / (R_MEAN + h_mean)))
    orbit = dict(mean_motion_rev_per_day=n, inclination_deg=inc, eccentricity=ecc, period_min=round(T / 60, 3),
                 semi_major_axis_km=round(a, 1), height_above_equatorial_radius_km=round(a - R_EQ, 1),
                 height_above_mean_radius_km=round(h_mean, 1),
                 perigee_apogee_height_km=[round(a * (1 - ecc) - R_EQ, 1), round(a * (1 + ecc) - R_EQ, 1)],
                 j2_node_drift_deg_per_day=round(drift, 4), sun_synchronous_rate_deg_per_day=round(SUN_RATE, 4),
                 horizon_angle_deg=round(lam, 2), longest_possible_pass_min=round(2 * lam / 360 * T / 60, 2),
                 range_ratio_horizon_to_overhead=round((math.sqrt((R_MEAN + h_mean) ** 2 - R_MEAN ** 2)) / h_mean, 2))
    passes = list(csv.DictReader(open(os.path.join(folder, "passes.csv"))))
    orbit["longest_pass_in_data_min"] = round(max(float(p["duration_s"]) for p in passes) / 60, 2)

    out = dict(run=os.path.basename(folder), tle_epoch_utc=info["tle_epoch_utc"], shadow=shadow, distance=distance,
               orbit=orbit)
    with open(os.path.join(folder, "checks.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    return out


if __name__ == "__main__":
    for f in sys.argv[1:] or [os.path.dirname(p) for p in glob.glob(os.path.join(ROOT, "real_passes", "*", "run_info.json"))]:
        print(json.dumps(check(os.path.abspath(f)), indent=1))
