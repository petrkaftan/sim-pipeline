import docker
import os
from pathlib import Path
import threading
from tools import run_convergence_monitor
from tools import is_mesh_ok
from tools import get_safe_timestep


status = False


convergence_check_interval = 1

def openfoamSimulation(simulation_name, simulation_working_directory, convergence_tolerance, rpm_count, convergence_window_revolutions, MODE, NUMBER_OF_CORES, resume, MESH_ONLY, ALLOW_BAD_MESH, STOP_ON_CONVERGENCE=False, initialize_from_previous=False, previous_simulation_path=None):

    # Docker client is setup here, interface volume mapping is defined, container is created:

    client = docker.from_env()

    # Define the volume mapping
    my_volumes = {
        simulation_working_directory: {'bind': '/simulation', 'mode': 'rw'}
    }

    # Create and start the container
    container = client.containers.run(
        image="microfluidica/openfoam:13",
        name=simulation_name,
        volumes=my_volumes,
        working_dir="/simulation", # Added this so it starts in the right folder
        command="bash", 
        detach=True,    
        tty=True,       
        stdin_open=True 
    )

    # Now these print statements will work because 'container' is defined here
    print(f"Container '{container.name}' created successfully!")
    print(f"Status: {container.status}")

    ### IF NOT RESUME ###

    if not resume:


        # Running the different openFOAM simulation commands (if Output is wanted, uncomment for line in result paragraph and comment for _ in result.output):

        blockMesh_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && blockMesh > log.blockMesh'"

        print("blockMesh started...")

        result = container.exec_run(blockMesh_cmd, stream=True)

        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        print("blockMesh finished...")

        surfaceFeatures_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && surfaceFeatures > log.surfaceFeatures'"

        print("surfaceFeatures started...")

        result = container.exec_run(surfaceFeatures_cmd, stream=True)

        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        print("surfaceFeatures finished...")

        snappyHexMesh_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && snappyHexMesh > log.snappyHexMesh'"

        print("snappyHexMesh started...")

        result = container.exec_run(snappyHexMesh_cmd, stream=True)

        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        print("snappyHexMesh finsished...")

        checkMesh_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && checkMesh | tee log.checkMesh'"

        


        result = container.exec_run(checkMesh_cmd, stream=True)

        for line in result.output:
            print(line.decode('utf-8').strip())

        #"""

        checkMesh_log_path = os.path.join(simulation_working_directory, 'log.checkMesh')

        if is_mesh_ok(Path(checkMesh_log_path)) or ALLOW_BAD_MESH:

            if MODE == "AMI":

                createNonConformalCouples_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && createNonConformalCouples innerCylinder innerCylinder_slave > log.createNonConformalCouples'"

                print("createNonConformalCouples started...")

                result = container.exec_run(createNonConformalCouples_cmd, stream=True)

                #for line in result.output:
                #   print(line.decode('utf-8').strip())

                for _ in result.output:
                    pass

                print("createNonConformalCouples finished...")

            
            if initialize_from_previous:
                print(f"Initializing from previous case: {previous_simulation_path}")


                mapFields_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && mapFields /simulation/init/ -consistent -sourceTime latestTime  > log.mapFields'"

                print("mapFields started...")

                result = container.exec_run(mapFields_cmd, stream=True)

                for _ in result.output:
                    pass

                print("mapFields finished...")


            if not MESH_ONLY:

                decomposePar_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && decomposePar > log.decomposePar'"

                print("decomposePar started...")

                result = container.exec_run(decomposePar_cmd, stream=True)

                #for line in result.output:
                #   print(line.decode('utf-8').strip())

                for _ in result.output:
                    pass

                print("decomposePar finished...")
        else:
            print("Mesh is not OK... stopping this case")
    else:
        print("Preparing to resume...")

        safe_time = get_safe_timestep(simulation_working_directory)

        reconstructPar_resume_cmd = f"bash -c 'source /opt/openfoam13/etc/bashrc && reconstructPar -time {safe_time}  > log_resume.reconstructPar'"

        print("Reconstructing safe timestep...")
        
        result = container.exec_run(reconstructPar_resume_cmd, stream=True)

        for _ in result.output:
            pass

        print("Reconstructing safe timestep finished...")

        print("Deleting processor folders...")

        delete_processor_folders_cmd = f"bash -c 'source /opt/openfoam13/etc/bashrc && rm -rf processor* > log.deleteProcessors'"

        result = container.exec_run(delete_processor_folders_cmd, stream=True)

        for _ in result.output:
            pass

        print("Deleted processor folder...")

        decomposePar_resume_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && decomposePar > log_resume.decomposePar'"

        print("decomposePar started...")

        result = container.exec_run(decomposePar_resume_cmd, stream=True)

        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        print("decomposePar finished...")







    ### IF NOT RESUME END ###

    ### IF NOT MESH_ONLY : ###

    if not MESH_ONLY:


        # Launch convergenceStop script in parallel (threading)


        if resume:
            timestep_str = str(safe_time)
        else:
            timestep_str = "0"


        monitor_thread = None
        if STOP_ON_CONVERGENCE:
            monitor_thread = threading.Thread(
                target=run_convergence_monitor,
                kwargs={
                    'main_sim_folder': simulation_working_directory,
                    'rpm':rpm_count,
                    'avg_history_count': convergence_window_revolutions,
                    'tolerance': convergence_tolerance,
                    'check_interval': convergence_check_interval,
                    'timestep' : timestep_str
                }
            )

            # Setting daemon=True ensures the monitor dies if the main script crashes
            monitor_thread.daemon = True

            # Starting convergence monitoring
            print(f"Launching Background Convergence Monitor... Timestep is: {timestep_str}")
            monitor_thread.start()
        else:
            print("Convergence early-stop monitor disabled. Solver will run to configured endTime.")

        # Starting the actual solving process


        simRun_cmd = f"bash -c 'source /opt/openfoam13/etc/bashrc && mpirun --allow-run-as-root --use-hwthread-cpus -np {NUMBER_OF_CORES} foamRun -solver incompressibleFluid -parallel | tee log.pimpleFoam'"

        print("pimpleFoamSolver started...")

        result = container.exec_run(simRun_cmd, stream=True)


        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        # The solver has now exited. 
        # If the monitor thread is NO LONGER alive, it means it found convergence and returned True.

        if monitor_thread is not None and not monitor_thread.is_alive():
            print("SUCCESS: Simulation stopped early due to convergence.")
        else:
            print("NOTICE: Simulation finished normally (reached original endTime).")

        status = True


        reconstructPar_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && reconstructPar > log.reconstructPar'"

        print("reconstructPar started...")

        result = container.exec_run(reconstructPar_cmd, stream=True)

        #for line in result.output:
        #   print(line.decode('utf-8').strip())

        for _ in result.output:
            pass

        print("reconstructPar finsished...")
    else: 
        status = True


    # Create .FOAM file

    foam_file_cmd = "bash -c 'source /opt/openfoam13/etc/bashrc && touch sim.foam'"


    result = container.exec_run(foam_file_cmd, stream=True)

    for _ in result.output:
        pass

    print("FOAM File created...")

        

    # Stop and Remove active simulation container

    print(f"Stopping container '{container.name}'...")
    container.stop()

    print(f"Removing container '{container.name}'...")
    container.remove()

    print("Cleanup complete. System ready for the next simulation.")

    return status
