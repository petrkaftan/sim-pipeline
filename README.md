# UAV Propeller CFD Pipeline

## Overview

Automated pipeline for generating meshes and running OpenFOAM simulations of UAV propellers.

### Features

- MRF (steady) and AMI (transient) simulation modes  
- Fully automated meshing (blockMesh + snappyHexMesh)  
- Parallel execution  
- Convergence monitoring (thrust + residuals)  
- Postprocessing & PDF report generation  
- Parameter study support  
- Robust resume capability  
- Mesh-only mode for tuning  

---

## Requirements

- Docker Engine **running**
- Conda environment:

```bash
conda env create -f of_pipeline_env.yml
conda activate of_pipeline_env
docker info
```

---

## CLI Design

The CLI is structured into:

### 1. Configuration Parameters (define the simulation setup)

```bash
--sim-dir        Output directory
--geometries     STL names (without .stl)
--rpms           Rotation speeds
--mode           AMI | MRF
--cores          Number of cores
--field-init     on | off (default: on)
--turbulence     kOmegaSST | kEpsilon
--end-time       OpenFOAM endTime in seconds (default: 0.2)
```

### 2. Feature Flags (activated if present)

```bash
--study          Enable parameter study
--resume         Resume existing simulation batch
--extend-completed Resume completed cases to a higher --end-time
--skip-postprocessing Skip report generation during simulation runs
--postprocess-only Run postprocessing later for an existing batch
--mesh-only      Stop after mesh generation
--allow-bad-mesh Neglects bad mesh checks before solving
--keep-rotation-steps Number of final 20-degree rotation write times to keep
--stop-on-convergence Enable early stopping from the convergence monitor
```

---

## Basic Usage

```bash
python main.py   --sim-dir <path>   --geometries <list>   --rpms <list>   --mode <AMI|MRF>   --cores <int> --turbulence <kOmegaSST|kEpsilon>  --field-init <on|off> --end-time <seconds>
```


---

## Turbulence Models & Wall Treatment

### kOmegaSST (Low-Re, no wall functions)

- Fully resolves the boundary layer
- Requires **y+ ≈ 1**
- Higher computational cost
- Used for accurate simulations

---

### kEpsilon (Wall function approach)

- Uses wall functions
- Does not resolve viscous sublayer
- Requires **y+ ≈ 30–100**
- Faster and more robust

---

## Important Concept

- Turbulence model and wall treatment are conceptually different
- In this pipeline:

```
kOmegaSST → no wall functions
kEpsilon  → wall functions
```

This is handled automatically via template selection.

---

## Template Selection

Templates follow:

```
Core Template <MODE> - <TURBULENCE>
```

Examples:

- Core Template AMI - kOmegaSST
- Core Template MRF - kEpsilon

---


## Configuration Options

### `--field-init`

Controls sequential initialization between RPM cases.

- `on` → initialize from previous RPM result  
- `off` → start each case independently  

---

## Feature Flags

### `--resume`

Resumes an interrupted simulation batch.

```bash
python main.py --sim-dir <path> --resume
```

To extend a completed batch, provide a higher end time:

```bash
python main.py --sim-dir <path> --resume --end-time 0.2 --extend-completed
```

If a resumed batch already contains completed cases, increasing `--end-time`
requires `--extend-completed` so the batch remains consistent.

### `--skip-postprocessing`

Skips the full postprocessing/report pipeline during simulation runs. Cases are
marked as `postprocessing_skipped` after solver reconstruction, and the batch
continues directly to the next case.

```bash
python main.py --sim-dir <path> <simulation options> --skip-postprocessing
```

### `--postprocess-only`

Runs only the postprocessing pipeline for an existing batch. It does not start
OpenFOAM or modify solver setup.

```bash
python main.py --sim-dir <path> --postprocess-only
```

### `--mesh-only`

Stops pipeline after mesh generation.

Use this for:
- Mesh tuning
- y⁺ validation
- Pre-solver checks

Solver must be started manually afterward.

---

### `--keep-rotation-steps`

The solver runs to `--end-time` seconds, defaulting to `0.2`. Each case writes main time
directories every 20 degrees of rotation:

```bash
writeInterval = 60 / (RPM * 18)
```

`purgeWrite` is set from `--keep-rotation-steps`, so only the last N of those
20-degree snapshots are retained.

```bash
python main.py \
  --sim-dir /scratch/simulations \
  --geometries 10x7E \
  --rpms 7000 \
  --mode AMI \
  --turbulence kOmegaSST \
  --cores 24 \
  --end-time 0.2 \
  --keep-rotation-steps 18
```

Use `--stop-on-convergence` only if you want the older behavior where the
convergence monitor can shorten the run before `0.2` seconds.

---

## Resume Feature

The pipeline automatically resumes simulations:

### Behavior

- Detects latest valid timestep (ignores `0`)
- Verifies required fields (`U`, `p`)
- Skips corrupted/incomplete timesteps
- Continues from last valid state

### Important ⚠️

> **One simulation run = one directory**

Always use a new folder for a new run.

---

## Study Mode

Enable parameter studies with:

```bash
--study
```

### Required Arguments

```bash
--study-parameter <name>
--study-file <file>
--study-values <values>
```

### Value Format

Values are separated by `...`

Examples:

```bash
7...8...9
(10 12 10)...(12 14 12)
```

---

## Study Behavior

- Requires exactly **one geometry** and **one RPM**
- Creates one simulation per value
- Folder naming:

```bash
<geometry>_<rpm>RPM_<parameter>_<value>
```

---

## Examples

### Standard Run

```bash
python main.py   --sim-dir /scratch/simulations   --geometries 10x7E   --rpms 7000   --mode AMI   --cores 24 --turbulence kOmegaSST
```

---

## Examples

### High-fidelity (kOmegaSST & AMI)

```bash
python main.py \
  --sim-dir /scratch \
  --geometries 10x7E \
  --rpms 7000 \
  --mode AMI \
  --cores 24 \
  --turbulence kOmegaSST
```

---

### Fast (kEpsilon & MRF)

```bash
python main.py \
  --sim-dir /scratch \
  --geometries 10x7E \
  --rpms 7000 \
  --mode MRF \
  --cores 24 \
  --turbulence kEpsilon
```

---

### Resume Run

```bash
python main.py   --sim-dir /scratch/simulations   --resume
```

### Extend Completed Run

```bash
python main.py   --sim-dir /scratch/simulations   --resume   --end-time 0.2   --extend-completed
```

### Simulation-Only Run

```bash
python main.py   --sim-dir /scratch/simulations   --geometries 10x7E   --rpms 7000   --mode MRF   --turbulence kEpsilon   --cores 24   --skip-postprocessing
```

### Postprocess Existing Run

```bash
python main.py   --sim-dir /scratch/simulations   --postprocess-only
```

---

### Mesh-Only Run

```bash
python main.py   --sim-dir /scratch/simulations   --geometries 10x7E   --rpms 7000   --mode AMI  --turbulence kOmegaSST --cores 24   --mesh-only
```

---

### Allow-Bad-Mesh Run

```bash
python main.py   --sim-dir /scratch/simulations   --geometries 10x7E   --rpms 7000   --mode AMI  --turbulence kOmegaSST --cores 24   --allow-bad-mesh
```

---

### Parameter Study

```bash
python main.py   --sim-dir /scratch/simulations   --geometries 10x7E   --rpms 7000   --mode AMI --turbulence kOmegaSST  --cores 24   --study   --study-parameter refinementLevel   --study-file snappyHexMeshDict   --study-values 3...4...5
```

---

## Notes

- STL files must be located in `STLs/`
- Names must match exactly (e.g. `10x7E.stl`)
- RPM order matters if `--field-init on`
- Simulation parameters are defined in `Parameters/`

### Simulation Modes

- **AMI** → more accurate, transient, slower  
- **MRF** → faster, steady, good for initial studies  

---

## Summary

- Use **configuration options** to define the simulation  
- Use **flags** to activate pipeline features  
- Keep simulation runs isolated per directory  

---

## Future Extensions

Planned improvements:

- Automated y⁺ targeting
