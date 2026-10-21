# FYProject_SSA_Training

Final-year project on Space Situational Awareness (SSA): simulating how bright a satellite looks from the
ground as it moves, spins and is lit by the Sun, using Blender renders of NASA's Aqua and Suomi NPP satellites.

## Folders

| Folder           | What is in it                                                                          |
|------------------|----------------------------------------------------------------------------------------|
| `script_code/`   | Blender scripts that build the scene, render and measure brightness. See `CODE_GUIDE.md`. |
| `plots/`         | Python scripts that turn the measured data into graphs (run outside Blender).          |
| `models/`        | The satellite models: Aqua detailed (115k triangles), Suomi NPP low-poly (4k).         |
| `material_tests/`| Flat plate, matte sphere and shiny panel: brightness vs spin angle and distance.       |
| `fidelity_test/` | Detailed vs simplified Aqua models: how much the brightness curve changes.            |
| `renders/`       | Still renders (EEVEE and Cycles), the dawn-dusk pass and the Sun sweep, with videos.   |

`satellite_comparison.blend` is the Blender scene with both satellites loaded.

All results are simulated with Blender's EEVEE renderer, not measured from real satellites.
