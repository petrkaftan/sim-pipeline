import argparse
from pathlib import Path

from preprocessing import preprocessing
from openfoamSimulation import openfoamSimulation
from postprocessing import postprocessing
from mesh_visualization import render_mesh_sections
from tools import create_simulation_order
from tools import load_simulation_order
from tools import save_simulation_order
from tools import update_case_status
from tools import has_timestep
from tools import reset_case_folder
from tools import get_safe_timestep
from tools import update_parameter

def main() -> None:
    pipeline_main_directory = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description="Dispatch OpenFOAM simulations.")

    parser.add_argument(
        "--sim-dir",
        type=Path,
        required=True,
        help="Directory where simulation cases will be created or resumed.",
    )
    parser.add_argument("--geometries", nargs="+")
    parser.add_argument("--rpms", nargs="+", type=int)
    parser.add_argument("--mode", choices=["AMI", "MRF"])
    parser.add_argument("--turbulence", choices = ["kEpsilon", "kOmegaSST"])
    parser.add_argument("--field-init", default="on", choices=["on", "off"])
    parser.add_argument("--study", action="store_true")
    parser.add_argument("--study-file")
    parser.add_argument("--study-parameter")
    parser.add_argument("--study-values", help="Study values separated by '...'. Example: '(8 24 8)...(16 48 16)'",)
    parser.add_argument("--cores", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--mesh-only", action="store_true")
    parser.add_argument("--allow-bad-mesh", action="store_true")
    parser.add_argument(
        "--end-time",
        type=float,
        help="OpenFOAM endTime for every case. Defaults to 0.2 for new batches.",
    )
    parser.add_argument(
        "--extend-completed",
        action="store_true",
        help="With --resume, rerun completed cases from their latest timestep using the requested --end-time.",
    )
    parser.add_argument(
        "--keep-rotation-steps",
        type=int,
        default=18,
        help="Number of final write times to keep. Each write is spaced by 20 degrees of rotation.",
    )
    parser.add_argument(
        "--stop-on-convergence",
        action="store_true",
        help="Enable the old convergence monitor behavior that stops the solver before endTime.",
    )
    parser.add_argument(
        "--pvpython",
        help="Optional path to ParaView pvpython for automatic mesh section PNGs.",
    )


    args = parser.parse_args()
    simulations_directory = args.sim_dir.resolve()

    # -------- RESUME / NEW RUN VALIDATION --------
    if args.resume:
        if not simulations_directory.exists():
            parser.error(f"--sim-dir does not exist: {simulations_directory}")

        order_file = simulations_directory / "simulation_order.json"
        if not order_file.exists():
            parser.error(
                f"--resume was used, but no simulation_order.json was found in {simulations_directory}"
            )

        order = load_simulation_order(simulations_directory)

        stored_end_time = order.get("end_time", 0.2)
        if args.extend_completed and args.end_time is None:
            parser.error("--extend-completed requires a new --end-time")

        if args.end_time is None:
            args.end_time = stored_end_time

        if args.end_time <= 0:
            parser.error("--end-time must be greater than 0")

        if args.end_time < stored_end_time:
            parser.error(
                f"--end-time {args.end_time} is lower than the stored batch end_time "
                f"{stored_end_time}. Use a new --sim-dir for a shorter run."
            )

        has_completed_cases = any(
            case.get("status") == "postprocessing_done"
            for case in order["cases"]
        )

        if (
            args.end_time > stored_end_time
            and has_completed_cases
            and not args.extend_completed
        ):
            parser.error(
                "This batch already has completed cases. Use --extend-completed "
                "when increasing --end-time so completed cases are resumed too."
            )

        if args.extend_completed and args.end_time <= stored_end_time:
            parser.error(
                f"--extend-completed requires --end-time to be greater than the "
                f"stored batch end_time {stored_end_time}."
            )

        args.mode = order["mode"]
        args.geometries = order["geometries"]
        args.rpms = order["rpms"]
        args.field_init = order.get("field_init", "on")
        args.study = order.get("study", False)
        args.study_file = order.get("study_file")
        args.study_parameter = order.get("study_parameter")
        args.study_values = order.get("study_values")
        args.cores = order["cores"]
        args.mesh_only = order["mesh_only"]
        args.allow_bad_mesh = order["allow_bad_mesh"]
        args.turbulence = order["turbulence"]
        args.keep_rotation_steps = order.get("keep_rotation_steps", 18)
        args.stop_on_convergence = order.get("stop_on_convergence", False)
        args.pvpython = getattr(args, "pvpython", None)

        order["end_time"] = args.end_time
        order["keep_rotation_steps"] = args.keep_rotation_steps
        order["stop_on_convergence"] = args.stop_on_convergence

        for case in order["cases"]:
            case["end_time"] = args.end_time
            case["keep_rotation_steps"] = args.keep_rotation_steps
            case["stop_on_convergence"] = args.stop_on_convergence
            if args.extend_completed and case.get("status") == "postprocessing_done":
                case["status"] = "solver_running"

        save_simulation_order(simulations_directory, order)

        print(f"\n--- Resuming simulation batch from: {simulations_directory} ---")
        print(f"Mode: {args.mode}")
        print(f"Geometries: {args.geometries}")
        print(f"RPMs: {args.rpms}")
        print(f"Cores: {args.cores}")
        print(f"End time: {args.end_time}")
        print(f"Study: {args.study}")

    else:
        if args.extend_completed:
            parser.error("--extend-completed can only be used with --resume")

        missing = []
        if args.geometries is None:
            missing.append("--geometries")
        if args.rpms is None:
            missing.append("--rpms")
        if args.mode is None:
            missing.append("--mode")
        if args.cores is None:
            missing.append("--cores")
        if args.turbulence is None:
            missing.append("--turbulence")

        if missing:
            parser.error(
                "The following arguments are required for a new simulation run: "
                + ", ".join(missing)
            )

        if args.study:
            study_missing = []
            if args.study_file is None:
                study_missing.append("--study-file")
            if args.study_parameter is None:
                study_missing.append("--study-parameter")
            if args.study_values is None:
                study_missing.append("--study-values")

            if study_missing:
                parser.error(
                    "The following arguments are required when --study is set: "
                    + ", ".join(study_missing)
                )

            if len(args.geometries) != 1 or len(args.rpms) != 1:
                parser.error(
                    "When --study is set, exactly one geometry and one RPM must be provided."
                )

        if args.keep_rotation_steps < 1:
            parser.error("--keep-rotation-steps must be at least 1")

        if args.end_time is None:
            args.end_time = 0.2

        if args.end_time <= 0:
            parser.error("--end-time must be greater than 0")

        simulations_directory.mkdir(parents=True, exist_ok=True)
        create_simulation_order(args=args, simulations_directory=simulations_directory)
        order = load_simulation_order(simulations_directory)

    convergence_monitoring_revolutions_count = 1000
    convergence_tolerance = 1e-3

    previous_simulation_by_geometry = {}

    # -------- UNIFIED CASE-BASED PIPELINE --------
    for case in order["cases"]:
        folder_name = case["folder"]
        geometry = case["geometry"]
        rpm = int(case["rpm"])
        mode = case.get("mode", args.mode)
        status = case.get("status", "pending")

        simulation_path = simulations_directory / folder_name
        simulation_path.mkdir(parents=True, exist_ok=True)

        control_parameters_path = simulation_path / "Parameters" / "controlDict.cpp"
        if control_parameters_path.exists():
            rotation_snapshot_interval = 60.0 / (rpm * 18.0)
            update_parameter(control_parameters_path, "endTime", args.end_time)
            update_parameter(
                control_parameters_path,
                "writeInterval",
                f"{rotation_snapshot_interval:.12g}",
            )
            update_parameter(control_parameters_path, "purgeWrite", int(args.keep_rotation_steps))

        stl_path = pipeline_main_directory / "STLs" / f"{geometry}.stl"
        is_study_case = "study_value" in case

        print(f"\n--- Case: {folder_name} | Status: {status} ---")

        if status == "postprocessing_done":
            print("Skipping completed case.")
            if not is_study_case:
                previous_simulation_by_geometry[geometry] = simulation_path
            continue

        previous_simulation_path = previous_simulation_by_geometry.get(geometry)
        use_previous_init = (
            args.field_init == "on"
            and previous_simulation_path is not None
            and not is_study_case
        )

        # Inner loop allows a clean restart to return to preprocessing
        # for the same case instead of moving to the next case.
        while status != "postprocessing_done":

            # ---------------- PREPROCESSING ----------------
            if status == "pending":
                print("Starting preprocessing...")

                preprocessing_kwargs = dict(
                    STL_PATH=stl_path,
                    RPM_COUNT=rpm,
                    MAIN_DIRECTORY=pipeline_main_directory,
                    TARGET_DIRECTORY=simulation_path,
                    CORES_TO_USE=args.cores,
                    MODE=mode,
                    INIT_FROM_PREVIOUS=use_previous_init,
                    PREVIOUS_SIMULATION_PATH=previous_simulation_path,
                    TURBULENCE_MODEL=args.turbulence,
                    END_TIME=args.end_time,
                    KEEP_ROTATION_STEPS=args.keep_rotation_steps,
                )

                if is_study_case:
                    preprocessing_kwargs.update(
                        STUDY_PARAMETER_NAME=case["study_parameter"],
                        STUDY_PARAMETER_FILE=case["study_file"],
                        STUDY_PARAMETER=case["study_value"],
                    )

                preprocessing(**preprocessing_kwargs)
                update_case_status(simulations_directory, folder_name, "preprocessing_done")
                status = "preprocessing_done"
                continue

            # ---------------- SOLVER START ----------------
            if status == "preprocessing_done":
                print("Starting OpenFOAM...")
                update_case_status(simulations_directory, folder_name, "solver_running")

                success = openfoamSimulation(
                    resume=False,
                    simulation_name=folder_name,
                    simulation_working_directory=simulation_path,
                    convergence_tolerance=convergence_tolerance,
                    rpm_count=rpm,
                    convergence_window_revolutions=convergence_monitoring_revolutions_count,
                    MODE=mode,
                    initialize_from_previous=use_previous_init,
                    previous_simulation_path=previous_simulation_path,
                    NUMBER_OF_CORES=args.cores,
                    MESH_ONLY=args.mesh_only,
                    ALLOW_BAD_MESH=args.allow_bad_mesh,
                    STOP_ON_CONVERGENCE=args.stop_on_convergence,
                )

                if success:
                    render_mesh_sections(
                        simulation_path,
                        pvpython_executable=args.pvpython,
                    )
                    update_case_status(simulations_directory, folder_name, "solver_done")
                    status = "solver_done"

                    if args.mesh_only:
                        update_case_status(simulations_directory, folder_name, "postprocessing_done")
                        status = "postprocessing_done"


                else:
                    update_case_status(simulations_directory, folder_name, "solver_running")
                    break

                continue

            # ---------------- SOLVER RESUME ----------------
            if status == "solver_running":

                processor0_path = simulation_path / "processor0"

                if not has_timestep(processor0_path):
                    print("Solver marked as running but no timesteps found → clean restart")

                    reset_case_folder(simulation_path)

                    update_case_status(simulations_directory, folder_name, "pending")
                    status = "pending"
                    continue

                

                # adjust safe timestep to resume from

                safe_time = get_safe_timestep(simulation_path)

                if safe_time is None:
                    # timesteps exist but none are usable -> clean restart
                    print("Timesteps exist but none are usable→ clean restart")

                    reset_case_folder(simulation_path)

                    update_case_status(simulations_directory, folder_name, "pending")
                    status = "pending"
                    continue
                else:
                    # commands if valid timesteps are there and standard resume:
                    print("Resuming solver from latest timestep")
                

                success = openfoamSimulation(
                    resume=True,
                    simulation_name=folder_name,
                    simulation_working_directory=simulation_path,
                    convergence_tolerance=convergence_tolerance,
                    rpm_count=rpm,
                    convergence_window_revolutions=convergence_monitoring_revolutions_count,
                    MODE=mode,
                    initialize_from_previous=use_previous_init,
                    previous_simulation_path=previous_simulation_path,
                    NUMBER_OF_CORES=args.cores,
                    MESH_ONLY=args.mesh_only,
                    ALLOW_BAD_MESH=args.allow_bad_mesh,
                    STOP_ON_CONVERGENCE=args.stop_on_convergence,
                )

                if success:
                    render_mesh_sections(
                        simulation_path,
                        pvpython_executable=args.pvpython,
                    )
                    update_case_status(simulations_directory, folder_name, "solver_done")
                    status = "solver_done"

                    if args.mesh_only:
                        update_case_status(simulations_directory, folder_name, "postprocessing_done")
                        status = "postprocessing_done"


                else:
                    update_case_status(simulations_directory, folder_name, "solver_running")
                    break

                continue

            


            # ---------------- POSTPROCESSING ----------------
            if status == "solver_done":
                print("Starting postprocessing...")
                postprocessing(
                    SIMULATION_WORKING_DIRECTORY=simulation_path,
                    RPM_COUNT=rpm,
                    MODE=mode,
                    TURBULENCE_MODEL=args.turbulence
                )
                update_case_status(simulations_directory, folder_name, "postprocessing_done")
                status = "postprocessing_done"
                continue

            raise ValueError(f"Unknown case status for {folder_name}: {status}")

        if status == "postprocessing_done" and not is_study_case:
            previous_simulation_by_geometry[geometry] = simulation_path

    print("\nAll simulations completed.")


if __name__ == "__main__":
    main()
