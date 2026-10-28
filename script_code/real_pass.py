"""
real_pass.py - a real satellite, on its real current orbit, seen from a real place on Earth, over time.

  python script_code/real_pass.py AQUA                 (a name, or a catalogue number such as 27424)
  python script_code/real_pass.py 27424 --days 3 --step 5
  python script_code/real_pass.py AQUA --start 2026-10-29T00:00 --lat 53.384954 --lon -6.256542

Plain Python (not Blender).  Needs:  pip install skyfield   (brings sgp4, jplephem, numpy)

WHAT IT DOES
  1. Looks the satellite up on CelesTrak: its catalogue record (SATCAT: name, type, owner, launch, size) and its
     current orbital elements (a TLE).  Both are saved exactly as downloaded, with the download time, so every
     run can be traced back to its input.  A copy younger than MAX_TLE_AGE_H hours is reused instead of
     downloading again.
  2. Computes the orbit with SGP4 (Skyfield's implementation of the standard model that TLEs are made for).
  3. For the observer, finds every pass (rise above the horizon, highest point, set) in the time window, and
     samples each pass every STEP seconds:
       elevation and azimuth in the sky, distance (range), the satellite's height, whether the satellite is
       in sunlight or in Earth's shadow, the Sun's elevation at the observer (how dark the sky is), and the
       phase angle (Sun-satellite-observer, the angle the brightness work depends on).
  4. Marks a pass "visible" if, at some moment, the satellite is above the horizon, in sunlight, and the sky
     is dark enough (Sun more than DARK_SUN_ALT below the horizon: civil twilight or darker).

OUTPUT  real_passes/<NAME>_<catalogue number>/
  sources/        the downloaded TLE and SATCAT record, and fetch_log.json (URLs and download times)
  passes.csv      one row per pass: times, highest elevation, shortest range, sunlit / visible
  samples.csv     every sample of every pass
  run_info.json   everything needed to repeat the run: inputs, observer, versions, TLE age

ACCURACY  A TLE is a fit to recent tracking, and SGP4's predictions get worse the further they are from the
TLE's epoch, so the run reports the TLE's age (SGP4 as implemented in the sgp4 library: Vallado et al. 2006,
"Revisiting Spacetrack Report #3").  Skyfield's Sun position uses JPL's DE421 ephemeris (downloaded once into
real_passes/ephemeris/).
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import urllib.parse
import urllib.request

import numpy as np
from skyfield import __version__ as SKYFIELD_VERSION
from skyfield.api import EarthSatellite, Loader, wgs84

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "real_passes")

# Observer: Dublin City University (Glasnevin).  Coordinates from DCU's Wikipedia entry
# (53°23'06"N 6°15'24"W = 53.384954, -6.256542); the height is an assumption (it changes nothing that matters).
OBSERVER = dict(name="DCU Glasnevin, Dublin", lat=53.384954, lon=-6.256542, elev_m=60.0,
                source="https://en.wikipedia.org/wiki/Dublin_City_University (coordinates); height assumed")
DAYS = 3.0                  # length of the time window
STEP = 5.0                  # seconds between samples within a pass
MIN_ELEV = 0.0              # a pass starts and ends at this elevation (the horizon)
DARK_SUN_ALT = -6.0         # the sky counts as dark when the Sun is below this (end of civil twilight)
MAX_TLE_AGE_H = 2.0         # reuse a downloaded TLE younger than this instead of downloading again
GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
SATCAT_URL = "https://celestrak.org/satcat/records.php"
EPHEMERIS = "de421.bsp"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DCU-FYP-SSA-simulator (student project)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def lookup(query):
    """(name, catalogue number, TLE line 1, TLE line 2, SATCAT record or None, folder); saves what it downloads."""
    key = "CATNR" if str(query).isdigit() else "NAME"
    url = f"{GP_URL}?{urllib.parse.urlencode({key: query, 'FORMAT': 'TLE'})}"
    text = _get(url).strip()
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    if not lines or len(lines) % 3:
        raise SystemExit(f"CelesTrak had no orbit for {query!r}: {text[:200]}")
    sats = [lines[i:i + 3] for i in range(0, len(lines), 3)]
    if len(sats) > 1:                                         # a name can match several objects
        exact = [s for s in sats if s[0].strip().upper() == str(query).strip().upper()]
        if len(exact) != 1:
            names = "\n  ".join(f"{s[0].strip()}  (catalogue number {s[1][2:7].strip()})" for s in sats[:20])
            raise SystemExit(f"{query!r} matches {len(sats)} objects; use a catalogue number:\n  {names}")
        sats = exact
    name, l1, l2 = sats[0][0].strip(), sats[0][1], sats[0][2]
    norad = int(l1[2:7])
    folder = os.path.join(OUT, f"{name.replace(' ', '_').replace('/', '-')}_{norad}")
    src = os.path.join(folder, "sources")
    os.makedirs(src, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    log_path = os.path.join(src, "fetch_log.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else []

    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(src, f"tle_{stamp}.txt"), "w") as fh:
        fh.write(f"{name}\n{l1}\n{l2}\n")
    log.append(dict(what="TLE (current orbital elements)", url=url, fetched_utc=now.isoformat(),
                    file=f"tle_{stamp}.txt"))
    satcat = None
    try:
        surl = f"{SATCAT_URL}?{urllib.parse.urlencode({'CATNR': norad, 'FORMAT': 'JSON'})}"
        recs = json.loads(_get(surl))
        satcat = recs[0] if recs else None
        with open(os.path.join(src, f"satcat_{stamp}.json"), "w") as fh:
            json.dump(recs, fh, indent=1)
        log.append(dict(what="SATCAT record", url=surl, fetched_utc=now.isoformat(), file=f"satcat_{stamp}.json"))
    except Exception as exc:                                   # the orbit is enough to carry on
        print("SATCAT lookup failed (carrying on without it):", exc)
    with open(log_path, "w") as fh:
        json.dump(log, fh, indent=1)
    return name, norad, l1, l2, satcat, folder, stamp


def cached(query):
    """Reuse the newest saved TLE for this satellite if it is younger than MAX_TLE_AGE_H; else None."""
    if not os.path.isdir(OUT):
        return None
    for d in os.listdir(OUT):
        src = os.path.join(OUT, d, "sources", "fetch_log.json")
        if not os.path.exists(src):
            continue
        name, norad = d.rsplit("_", 1)
        if str(query).upper() not in (norad, name.replace("_", " ").upper()):
            continue
        log = [e for e in json.load(open(src)) if e["what"].startswith("TLE")]
        if not log:
            continue
        last = log[-1]
        age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last["fetched_utc"])).total_seconds() / 3600
        if age_h > MAX_TLE_AGE_H:
            return None
        n, l1, l2 = open(os.path.join(OUT, d, "sources", last["file"])).read().splitlines()[:3]
        sc = sorted(f for f in os.listdir(os.path.join(OUT, d, "sources")) if f.startswith("satcat_"))
        satcat = json.load(open(os.path.join(OUT, d, "sources", sc[-1])))[0] if sc else None
        print(f"Using the TLE downloaded {age_h:.1f} h ago ({last['file']})")
        return n.strip(), int(l1[2:7]), l1, l2, satcat, os.path.join(OUT, d), last["file"][4:-4]
    return None


def angle_deg(a, b):
    """Angle between two sets of vectors, shape (3, N)."""
    c = np.sum(a * b, axis=0) / (np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0))
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def run(query, days=DAYS, step=STEP, start=None, lat=None, lon=None, elev_m=None):
    hit = cached(query)
    name, norad, l1, l2, satcat, folder, stamp = hit or lookup(query)
    obs_info = dict(OBSERVER)
    if lat is not None:
        obs_info.update(name="custom", lat=lat, lon=lon if lon is not None else OBSERVER["lon"],
                        elev_m=elev_m if elev_m is not None else 0.0, source="given on the command line")

    load = Loader(os.path.join(OUT, "ephemeris"), verbose=False)
    ts = load.timescale()
    eph = load(EPHEMERIS)
    earth, sun = eph["earth"], eph["sun"]
    sat = EarthSatellite(l1, l2, name, ts)
    obs = wgs84.latlon(obs_info["lat"], obs_info["lon"], elevation_m=obs_info["elev_m"])

    t_start = (dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc) if start
               else dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0))
    t0, t1 = ts.from_datetime(t_start), ts.from_datetime(t_start + dt.timedelta(days=days))
    times, events = sat.find_events(obs, t0, t1, altitude_degrees=MIN_ELEV)

    # group the rise (0) / highest point (1) / set (2) events into whole passes
    passes, cur = [], None
    for t, e in zip(times, events):
        if e == 0:
            cur = dict(rise=t)
        elif e == 1 and cur is not None:
            cur.setdefault("tops", []).append(t)
        elif e == 2 and cur is not None:
            cur["set"] = t
            passes.append(cur)
            cur = None

    pass_rows, sample_rows = [], []
    for n, p in enumerate(passes, 1):
        secs = np.arange(0.0, (p["set"] - p["rise"]) * 86400.0 + step, step)
        t = ts.tt_jd(p["rise"].tt + np.minimum(secs, (p["set"] - p["rise"]) * 86400.0) / 86400.0)
        geo = sat.at(t)
        alt, az, rng = (sat - obs).at(t).altaz()
        sunlit = geo.is_sunlit(eph)
        sun_alt = (earth + obs).at(t).observe(sun).apparent().altaz()[0].degrees
        height = wgs84.height_of(geo).km
        sat_xyz = geo.position.km                                    # geocentric, km
        sun_xyz = (sun - earth).at(t).position.km                    # geocentric, km
        obs_xyz = obs.at(t).position.km
        phase = angle_deg(sun_xyz - sat_xyz, obs_xyz - sat_xyz)
        dark = sun_alt < DARK_SUN_ALT
        visible = sunlit & dark & (alt.degrees > MIN_ELEV)
        for k in range(len(secs)):
            sample_rows.append([n, t[k].utc_strftime("%Y-%m-%dT%H:%M:%SZ"), round(float(secs[k]), 1),
                                round(float(alt.degrees[k]), 3), round(float(az.degrees[k]), 3),
                                round(float(rng.km[k]), 2), round(float(height[k]), 2), int(sunlit[k]),
                                round(float(sun_alt[k]), 3), round(float(phase[k]), 3), int(dark[k]), int(visible[k])])
        top = int(np.argmax(alt.degrees))
        shadow_entry = ""
        if sunlit.any() and not sunlit.all():
            change = np.nonzero(np.diff(sunlit.astype(int)) == -1)[0]
            if len(change):
                shadow_entry = t[change[0] + 1].utc_strftime("%Y-%m-%dT%H:%M:%SZ")
        pass_rows.append([n, p["rise"].utc_strftime("%Y-%m-%dT%H:%M:%SZ"), t[top].utc_strftime("%Y-%m-%dT%H:%M:%SZ"),
                          p["set"].utc_strftime("%Y-%m-%dT%H:%M:%SZ"), round(float(secs[-1]), 0),
                          round(float(alt.degrees[top]), 2), round(float(az.degrees[top]), 1),
                          round(float(rng.km.min()), 1), round(float(sunlit.mean()), 3),
                          round(float(sun_alt[top]), 2), int(visible.any()), shadow_entry])

    with open(os.path.join(folder, "passes.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pass", "rise_utc", "highest_utc", "set_utc", "duration_s", "max_elev_deg", "azimuth_at_max_deg",
                    "min_range_km", "frac_sunlit", "sun_elev_at_max_deg", "visible", "enters_shadow_utc"])
        w.writerows(pass_rows)
    with open(os.path.join(folder, "samples.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pass", "time_utc", "seconds_from_rise", "elev_deg", "azimuth_deg", "range_km", "height_km",
                    "sunlit", "sun_elev_deg", "phase_deg", "sky_dark", "visible"])
        w.writerows(sample_rows)

    import sgp4
    epoch = sat.epoch.utc_datetime()
    info = dict(satellite=name, catalogue_number=norad, tle=[l1, l2], tle_epoch_utc=epoch.isoformat(),
                tle_file=f"sources/tle_{stamp}.txt",
                tle_age_at_start_days=round((t_start - epoch).total_seconds() / 86400, 3),
                satcat=satcat, observer=obs_info,
                window_start_utc=t_start.isoformat(), window_days=days, step_s=step, min_elev_deg=MIN_ELEV,
                dark_sun_alt_deg=DARK_SUN_ALT, ephemeris=EPHEMERIS, model="SGP4 (TLE)",
                versions=dict(skyfield=SKYFIELD_VERSION, sgp4=sgp4.__version__),
                passes=len(pass_rows), visible_passes=int(sum(r[10] for r in pass_rows)))
    with open(os.path.join(folder, "run_info.json"), "w") as fh:
        json.dump(info, fh, indent=1)
    return info, folder


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("satellite", help="a name (e.g. AQUA) or catalogue number (e.g. 27424)")
    p.add_argument("--days", type=float, default=DAYS)
    p.add_argument("--step", type=float, default=STEP)
    p.add_argument("--start", default=None, help="UTC, e.g. 2026-10-29T00:00 (default: now)")
    p.add_argument("--lat", type=float); p.add_argument("--lon", type=float); p.add_argument("--elev", type=float)
    a = p.parse_args()
    info, folder = run(a.satellite, a.days, a.step, a.start, a.lat, a.lon, a.elev)
    print(f"{info['satellite']} ({info['catalogue_number']}): {info['passes']} passes, {info['visible_passes']} visible, "
          f"TLE {info['tle_age_at_start_days']:.2f} days old -> {folder}")
