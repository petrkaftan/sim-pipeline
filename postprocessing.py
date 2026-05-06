from pathlib import Path

import docker

from createSimulationReport import create_simulation_report
from tools import merge_postprocessing_dat_files


def run_openfoam_derived_fields(case_path):
    case_path = Path(case_path)

    client = docker.from_env()
    container = client.containers.run(
        image="microfluidica/openfoam:13",
        volumes={case_path: {"bind": "/simulation", "mode": "rw"}},
        working_dir="/simulation",
        command="bash",
        detach=True,
        tty=True,
        stdin_open=True,
    )

    try:
        commands = [
            ("yPlus", "postProcess -func yPlus -latestTime > log.postProcess.yPlus"),
            (
                "wallShearStress",
                "postProcess -func wallShearStress -latestTime > log.postProcess.wallShearStress",
            ),
        ]

        for name, command in commands:
            print(f"Computing {name} for latest time...")
            result = container.exec_run(
                f"bash -c 'source /opt/openfoam13/etc/bashrc && {command}'",
                stream=True,
            )
            for _ in result.output:
                pass
    finally:
        container.stop()
        container.remove()


def postprocessing(SIMULATION_WORKING_DIRECTORY, RPM_COUNT, MODE, TURBULENCE_MODEL):

    run_openfoam_derived_fields(SIMULATION_WORKING_DIRECTORY)

    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "forcesBlades")
    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "residuals")
    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "yPlus")

    create_simulation_report(case_path=SIMULATION_WORKING_DIRECTORY,turbulence_model= TURBULENCE_MODEL, rpm=RPM_COUNT, mode=MODE)

    return None


