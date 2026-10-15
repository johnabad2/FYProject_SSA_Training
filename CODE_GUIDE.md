# Code guide

Everything lives in this folder. There are two kinds of script:

* **Blender scripts** (run inside Blender): they build the scene, render pictures and measure brightness.
* **Plot scripts** (`plots/`, run with any Python): they turn the measured data into the graphs.

## Running the Blender scripts

In Blender open the **Scripting** tab, open `run_tests.py`, set `TEST = "..."` and press **Alt+P**.

| `TEST =`      | Script it runs            | What it does                                                                                   |
|---------------|---------------------------|------------------------------------------------------------------------------------------------|
| `"setup"`     | `setup_scene.py`          | Black space world, one Sun lamp, camera framed on Aqua, satellites laid out apart.             |
| `"stills"`    | `render_angles.py`        | 6 stills of each satellite at different Sun angle, viewing angle and rotation.                  |
| `"dawn_dusk"` | `dawn_dusk_scenario.py`   | Dawn-dusk polar orbit: Sun, observer and spin for 10 moments of one visible pass.               |
| `"animation"` | `make_animation.py`       | The same pass as 240 frames, joined into `dawn_dusk_pass.mp4` (both satellites side by side).   |
| `"materials"` | `material_tests.py`       | Flat plate, matte sphere, shiny panel spun 360 degrees; sphere moved away. Writes CSV data.     |
| `"fidelity"`  | `fidelity_test.py`        | Detailed Aqua vs reduced versions at the same angles; brightness and washout with distance.     |

Not in the launcher (run from the Blender console with `runpy`):

| Script                | What it does                                                                                   |
|-----------------------|------------------------------------------------------------------------------------------------|
| `sun_sweep.py`        | Fixed satellite and camera; the Sun travels on an ellipse from overhead, round, underneath.     |
| `spin_animation.py`   | Frames for the spin animation (three Aqua versions spinning, Sun and camera fixed).             |

`render_angles.py` is the shared base: the other scripts call it for the Sun/camera placement and rendering.

## Making the graphs and videos (outside Blender)

Needs Python with numpy, matplotlib and Pillow (videos also need ffmpeg). Run from this folder:

| Command                                          | Reads                                   | Writes                                                                                         |
|--------------------------------------------------|-----------------------------------------|------------------------------------------------------------------------------------------------|
| `python plots/plot_material_tests.py`            | `material_tests/data/*.csv`, `samples/` | `material_tests/brightness_vs_angle.png`, `sample_renders.png`, `data/summary_stats.json`       |
| `python plots/plot_fidelity.py`                  | `fidelity_test/data/`                   | `fidelity_test/fidelity_main.png`, `fidelity_pictures.png`, `data/summary_stats.json`           |
| `python make_sun_sweep_media.py renders_sun_sweep` | `renders_sun_sweep/*.png`             | contact sheets and `sun_sweep.mp4`                                                              |
| `python make_spin_animation.py fidelity_test`    | `fidelity_test/animation_spin90/`       | `fidelity_test/spin_sun90.mp4`                                                                  |

## What each graph shows

* `brightness_vs_angle.png`: brightness against spin angle for the plate, the sphere and the shiny panel, plus a zoom on a glint and the sphere moving away (1/distance squared).
* `fidelity_main.png`: brightness curves of the detailed vs cheap models, error against triangle count, and how the error shrinks as the satellite gets further away.
* `fidelity_pictures.png`: one frame at coarser and coarser pixel blocks, with the error under each cheap model.

## Models used in the fidelity test

`A` detailed Aqua (115k triangles) is the reference. `N4k` is a plain automatic reduction (4k). `D30k`, `D10k`, `D5k`, `D4k` are reductions that keep the thin flat parts whole. `C` is Suomi NPP (a different satellite).

## Method in one paragraph

Brightness is the sum of all pixel values in a render (32-bit, linear, black background, one Sun lamp). Distance is simulated by adding pixels up in bigger and bigger blocks. All results are simulated with Blender's EEVEE renderer, not measured from real satellites.
