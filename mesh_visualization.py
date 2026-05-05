import os
import shutil
import subprocess
from pathlib import Path


SECTION_RENDER_SCRIPT = r"""
import math
import os
import sys

from paraview.simple import *


case_file = sys.argv[1]
output_dir = sys.argv[2]
os.makedirs(output_dir, exist_ok=True)


def try_set(proxy, name, value):
    try:
        setattr(proxy, name, value)
    except Exception:
        pass


foam = OpenFOAMReader(FileName=case_file)
try_set(foam, "MeshRegions", ["internalMesh"])
try_set(foam, "CellArrays", [])
UpdatePipeline(proxy=foam)

bounds = foam.GetDataInformation().GetBounds()
if bounds is None or len(bounds) != 6 or any(math.isnan(v) for v in bounds):
    raise RuntimeError("Could not read mesh bounds from OpenFOAM case.")

center = [
    0.5 * (bounds[0] + bounds[1]),
    0.5 * (bounds[2] + bounds[3]),
    0.5 * (bounds[4] + bounds[5]),
]
span = [
    max(bounds[1] - bounds[0], 1e-9),
    max(bounds[3] - bounds[2], 1e-9),
    max(bounds[5] - bounds[4], 1e-9),
]
distance = max(span) * 2.0

view = GetActiveViewOrCreate("RenderView")
view.ViewSize = [1600, 1200]
view.Background = [1.0, 1.0, 1.0]
view.OrientationAxesVisibility = 1


def save_section(name, normal, camera_position, camera_up):
    section = Slice(registrationName=name, Input=foam)
    section.SliceType = "Plane"
    section.SliceType.Origin = center
    section.SliceType.Normal = normal
    UpdatePipeline(proxy=section)

    display = Show(section, view)
    display.Representation = "Surface With Edges"
    try_set(display, "EdgeColor", [0.0, 0.0, 0.0])
    try_set(display, "DiffuseColor", [0.78, 0.78, 0.78])
    ColorBy(display, None)

    view.CameraPosition = camera_position
    view.CameraFocalPoint = center
    view.CameraViewUp = camera_up
    ResetCamera()
    Render()

    SaveScreenshot(
        os.path.join(output_dir, f"{name}.png"),
        view,
        ImageResolution=[1600, 1200],
    )

    Hide(section, view)
    Delete(section)


save_section(
    "mesh_section_xy",
    [0.0, 0.0, 1.0],
    [center[0], center[1], center[2] + distance],
    [0.0, 1.0, 0.0],
)
save_section(
    "mesh_section_xz",
    [0.0, 1.0, 0.0],
    [center[0], center[1] - distance, center[2]],
    [0.0, 0.0, 1.0],
)
"""


def find_pvpython(explicit_path=None):
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists():
            return str(candidate)

    env_path = os.environ.get("PVPYTHON") or os.environ.get("PV_PYTHON")
    if env_path and Path(env_path).exists():
        return env_path

    path_candidate = shutil.which("pvpython")
    if path_candidate:
        return path_candidate

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        for candidate in sorted(Path(program_files).glob("ParaView*/bin/pvpython.exe"), reverse=True):
            return str(candidate)

    return None


def render_mesh_sections(case_path, pvpython_executable=None):
    case_path = Path(case_path)
    foam_file = case_path / "sim.foam"
    if not foam_file.exists():
        print(f"Mesh section preview skipped: missing {foam_file}")
        return False

    pvpython = find_pvpython(pvpython_executable)
    if pvpython is None:
        print(
            "Mesh section preview skipped: pvpython was not found. "
            "Install ParaView or set PVPYTHON/PV_PYTHON to pvpython.exe."
        )
        return False

    output_dir = case_path / "mesh_sections"
    output_dir.mkdir(exist_ok=True)
    script_path = output_dir / "_render_mesh_sections.py"
    script_path.write_text(SECTION_RENDER_SCRIPT, encoding="utf-8")

    print("Rendering mesh section previews...")
    result = subprocess.run(
        [pvpython, str(script_path), str(foam_file), str(output_dir)],
        cwd=case_path,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        log_path = output_dir / "render_mesh_sections.log"
        log_path.write_text(
            "STDOUT:\n"
            + result.stdout
            + "\n\nSTDERR:\n"
            + result.stderr,
            encoding="utf-8",
        )
        print(f"Mesh section preview failed. See: {log_path}")
        return False

    print(f"Mesh section previews saved to: {output_dir}")
    return True
