# Code guide

The scripts live in `script_code/` and `plots/`; their results go into `material_tests/`, `fidelity_test/` and `renders/`. There are two kinds of script:

* **Blender scripts** (run inside Blender): they build the scene, render pictures and measure brightness.
* **Plot scripts** (`plots/`, run with any Python): they turn the measured data into the graphs.

## Running the Blender scripts

In Blender open the **Scripting** tab, open `run_tests.py`, set `TEST = "..."` and press **Alt+P**.

| `TEST =`      | Script it runs            | What it does                                                                                   |
|---------------|---------------------------|------------------------------------------------------------------------------------------------|
| `"setup"`     | `setup_scene.py`          | Black space world, one Sun lamp, camera framed on Aqua, satellites laid out apart.             |
| `"stills"`    | `render_angles.py`        | 6 stills of each satellite at different Sun angle, viewing angle and rotation.                  |
| `"dawn_dusk"` | `dawn_dusk_scenario.py`   | Dawn-dusk polar orbit: Sun, observer and spin for 10 moments of one visible pass.               |
| `"animation"` | `make_animation.py`       | The same pass as 240 frames (kept in `C:\SSA\animation_frames`), joined into `renders/renders_dawn_dusk/dawn_dusk_pass.mp4`. |
| `"materials"` | `material_tests.py`       | Flat plate, matte sphere, shiny panel spun 360 degrees; sphere moved away. Writes CSV data.     |
| `"fidelity"`  | `fidelity_test.py`        | Detailed Aqua vs reduced versions at the same angles; brightness and washout with distance.     |
| `"brightness_map"` | `brightness_map.py`  | Every Sun direction × every observer direction (48 × 48) for both satellites and six simple shapes. Stops after ~10 min; run again until `remaining` is 0. |
| `"light_curves"`   | `light_curves.py`    | Spin light curves about 24 axes at 3 phase angles, and the dawn-dusk pass stable / slowly spinning / tumbling. Both satellites. |

Not in the launcher (run from the Blender console with `runpy`):

| Script                | What it does                                                                                   |
|-----------------------|------------------------------------------------------------------------------------------------|
| `sun_sweep.py`        | Fixed satellite and camera; the Sun travels on an ellipse from overhead, round, underneath.     |
| `spin_animation.py`   | Frames for the spin animation (three Aqua versions spinning, Sun and camera fixed).             |
| `video_frames.py`     | Frames for the two explainer videos (`render_all()`), and MP4 encoding (`encode(name)`). Needs `light_curves.py` first. |

`render_angles.py` is the shared base: the other scripts call it for the Sun/camera placement and rendering.

## Real passes (outside Blender)

Needs `pip install skyfield` (brings sgp4).  Run from the project folder:

| Command | Writes |
|---|---|
| `python script_code/real_pass.py AQUA` (a name or catalogue number; options `--days`, `--step`, `--start`, `--lat/--lon/--elev`) | `real_passes/<NAME>_<number>/`: `passes.csv`, `samples.csv`, `run_info.json`, and `sources/` (the downloaded TLE and catalogue record, with download times) |
| `python plots/plot_real_pass.py` | `real_passes/<NAME>_<number>/passes_overview.png` |

The orbit is downloaded from CelesTrak (reused for 2 hours rather than downloaded again); the Sun's position file
(DE421) is downloaded once into `real_passes/ephemeris/`.

## Making the graphs and videos (outside Blender)

Needs Python with numpy, matplotlib and Pillow (videos also need ffmpeg). Run from the project folder (`FYProject_SSA_Training`):

| Command                                                                  | Reads                                   | Writes                                                                                   |
|--------------------------------------------------------------------------|-----------------------------------------|------------------------------------------------------------------------------------------|
| `python plots/plot_material_tests.py`                                    | `material_tests/data/*.csv`, `samples/` | `material_tests/brightness_vs_angle.png`, `sample_renders.png`, `data/summary_stats.json` |
| `python plots/plot_fidelity.py`                                          | `fidelity_test/data/`                   | `fidelity_test/fidelity_main.png`, `fidelity_pictures.png`, `data/summary_stats.json`     |
| `python plots/plot_brightness_map.py`                                    | `brightness_map/data/`                  | `brightness_map/brightness_map_satellites.png`, `brightness_map_shapes.png`, `data/summary_stats.json` |
| `python plots/plot_light_curves.py`                                      | `light_curves/data/`, `brightness_map/data/` | `light_curves/light_curve_degeneracy.png`, `stable_vs_tumbling.png`, `data/summary_stats.json` |
| `python script_code/make_videos.py`                                      | `videos/frames/`, `light_curves/data/`  | laid-out frames in `videos/composed/`; then `encode(...)` in Blender makes `videos/*.mp4` |
| `python script_code/make_sun_sweep_media.py renders/renders_sun_sweep`   | `renders/renders_sun_sweep/*.png`       | contact sheets and `sun_sweep.mp4` in the same folder                                     |
| `python script_code/make_spin_animation.py fidelity_test`                | `fidelity_test/animation_spin90/`       | `fidelity_test/spin_sun90.mp4`                                                            |

## What each graph shows

* `real_passes/<NAME>_<number>/passes_overview.png`: every pass of a real satellite over the observer on the sky, when the passes happen and how high they get, the highest visible pass moment by moment (elevation, distance, entering Earth's shadow), and zenith angle against distance with the formula as a check.

* `brightness_vs_angle.png`: brightness against spin angle for the plate, the sphere and the shiny panel, plus a zoom on a glint and the sphere moving away (1/distance squared).
* `fidelity_main.png`: brightness curves of the detailed vs cheap models, error against triangle count, and how the error shrinks as the satellite gets further away.
* `fidelity_pictures.png`: one frame at coarser and coarser pixel blocks, with the error under each cheap model.
* `brightness_map_satellites.png`: brightness of Aqua and Suomi NPP against phase angle for every orientation, how much orientation alone changes it, one Sun direction seen from every observer direction, and the degeneracy (how often different orientations look the same).
* `brightness_map_shapes.png`: the same brightness-against-phase view for each simple shape (sphere, plates, cube, cylinder, box-wing).
* `light_curve_degeneracy.png`: how many different spin axes fit a stretch of light curve, from one measurement (a snapshot) up to a whole turn.
* `stable_vs_tumbling.png`: the same pass for a stable, a slowly spinning and a tumbling satellite; what being Earth-pointing rules out; flicker as a way to tell them apart.
* `videos/stable_vs_tumbling.mp4`, `videos/telescope_view.mp4`: explainer videos with the measured light curve drawn under the renders.

## Models used in the fidelity test

`A` detailed Aqua (115k triangles) is the reference. `N4k` is a plain automatic reduction (4k). `D30k`, `D10k`, `D5k`, `D4k` are reductions that keep the thin flat parts whole. `C` is Suomi NPP (a different satellite).

## Method in one paragraph

Brightness is the sum of all pixel values in a render (32-bit, linear, black background, one Sun lamp). Distance is simulated by adding pixels up in bigger and bigger blocks. All results are simulated with Blender's EEVEE renderer, not measured from real satellites.
