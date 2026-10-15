"""
run_tests.py - one place to run every SSA test from inside Blender.

HOW TO USE
  1. Change TEST below to one of the names in the list.
  2. Press  Run Script  (Alt+P) with the mouse over this text.
  3. Watch the System Console (Window > Toggle System Console) for progress.

TESTS
  "setup"      black space world, Sun, camera, satellites laid out            (instant)
  "stills"     6 still renders of both satellites at different angles         (~1 min)
  "dawn_dusk"  10 frames of the dawn-dusk pass for both satellites            (~1 min)
  "animation"  render the 240 animation frames (resumable) and, when all
               exist, assemble dawn_dusk_pass.mp4                              (~10+ min)
  "materials"  flat plate / matte sphere / shiny panel spin sweeps + distance (~5 min)
  "fidelity"   detailed vs cheap model brightness comparison                  (~15 min)

Blender is busy (frozen) while a test runs; that is normal. Re-running an unfinished
"animation" or "fidelity" continues where it left off.
"""
import os
import runpy

HERE = r"C:\SSA\FYProject_SSA_Training"
TEST = "setup"                  # <-- change this


def load(name):
    return runpy.run_path(os.path.join(HERE, name), run_name="ssa_" + name)


def main(test=TEST):
    if test == "setup":
        return load("setup_scene.py")["setup"]()
    if test == "stills":
        return load("render_angles.py")["main"]()
    if test == "dawn_dusk":
        return load("dawn_dusk_scenario.py")["run"]()
    if test == "animation":
        ns = load("make_animation.py")
        res = ns["render_frames"](max_seconds=100)
        print(res)
        return ns["assemble"]() if res["remaining"] == 0 else res
    if test == "materials":
        ns = load("material_tests.py")
        out = [ns["spin_sweep"](k) for k in ("plate_diffuse", "sphere_diffuse", "panel_shiny")]
        out.append(ns["distance_sweep"]())
        return out
    if test == "fidelity":
        return load("fidelity_test.py")["run"]()
    raise ValueError(f"unknown TEST {test!r}")


print(main())
