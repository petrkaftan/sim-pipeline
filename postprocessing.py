from createSimulationReport import create_simulation_report
from tools import merge_postprocessing_dat_files



def postprocessing(SIMULATION_WORKING_DIRECTORY, RPM_COUNT, MODE):

    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "forcesBlades")
    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "residuals")
    merge_postprocessing_dat_files(SIMULATION_WORKING_DIRECTORY, "yPlus")

    create_simulation_report(case_path=SIMULATION_WORKING_DIRECTORY, rpm=RPM_COUNT, mode=MODE)

    return None


