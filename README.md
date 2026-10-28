# FYProject_SSA_Training

Final-year project on Space Situational Awareness (SSA): simulating how bright a satellite looks from the
ground as it moves, spins and is lit by the Sun, using Blender renders of NASA's Aqua and Suomi NPP satellites.

## Start here

| Document | What it is |
|---|---|
| [`docs/IDEAL_CASE.md`](docs/IDEAL_CASE.md) | Write-up of the results so far (ideal conditions) |
| [`docs/METHODS_AND_SOURCES.md`](docs/METHODS_AND_SOURCES.md) | The maths behind every result and a source for every outside value |
| [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) | Which script does what, and how to run it |

## Folders

| Folder           | What is in it                                                                          |
|------------------|----------------------------------------------------------------------------------------|
| `docs/`          | The three documents above.                                                             |
| `script_code/`   | Blender scripts that build the scene, render and measure brightness.                   |
| `plots/`         | Python scripts that turn the measured data into graphs (run outside Blender).          |
| `models/`        | The satellite models (NASA 3D Resources): Aqua detailed (115k triangles), Suomi NPP low-poly (4k). |
| `material_tests/`| Flat plate, matte sphere and shiny panel: brightness vs spin angle and distance.       |
| `fidelity_test/` | Detailed vs simplified Aqua models: how much the brightness curve changes.            |
| `brightness_map/`| Brightness for every Sun × observer direction: range of values and degeneracy.         |
| `light_curves/`  | Brightness over time: spins about many axes, and stable vs tumbling over a pass.       |
| `real_passes/`   | Real satellites on their current orbits, seen from DCU: every pass, sky position, distance, Earth's shadow. |
| `videos/`        | Explainer videos: stable vs tumbling, and what a ground telescope actually sees.        |
| `renders/`       | Still renders (EEVEE and Cycles), the dawn-dusk pass and the Sun sweep, with videos.   |

`satellite_comparison.blend` is the Blender scene with both satellites loaded; open this copy.

Each results folder has a `data/` folder (the measured numbers, as CSV) and a `data/summary_stats.json` (every
number quoted in the documents).  All results are simulated in Blender (EEVEE) under ideal conditions, not
measured from real satellites.
