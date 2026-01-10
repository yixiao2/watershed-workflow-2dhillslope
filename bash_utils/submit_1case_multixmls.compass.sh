#!/bin/bash
#SBATCH --account=ber200003
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --job-name=test-timestep
#SBATCH --time=24:00:00

source /etc/profile.d/modules.sh
module purge
source ~/set_ats_env/ats-1.5.2.compass.250212.sh

# Simplified approach - no function, direct execution
echo "Original directory: $(pwd)"

# Arrays to store background job PIDs
declare -a PIDS=()
declare -a CASES=("fixed1000s" "fixed100s" "fixed40s" "fixed10s" "standard.ini0min0")

ORIGINAL_DIR=$(pwd)

# Record overall start time
overall_start_time=$(date +%s)
echo "=== Overall job started at: $(date) ==="

# Launch all cases
for i in {0..4}; do
    case_name=${CASES[i]}
    echo "=== Launching ${case_name} ==="
    
    # Use subshell to isolate each case
    (
        cd "$ORIGINAL_DIR/$case_dir"
        echo "Working in: $(pwd)"
        
        # Setup NF01 directory
        DIR_NAME="NF01.${case_name}"
        DATE=$(date +%y%m%d%H%M%S)
        
        if [ -d "$DIR_NAME" ]; then
            if [ ! -z "$(ls -A "$DIR_NAME")" ]; then
                echo "Renaming existing directory to ${DIR_NAME}.${DATE}"
                mv "$DIR_NAME" "${DIR_NAME}.${DATE}"
                mkdir "$DIR_NAME"
            else
                echo "Directory $DIR_NAME exists and is empty"
            fi
        else
            echo "Creating directory $DIR_NAME"
            mkdir "$DIR_NAME"
        fi
        
        cd "$DIR_NAME"
        echo "Now in: $(pwd)"
        
	# XML file
        XML_FILE="${ORIGINAL_DIR}/NF01_nx100_nz18.run1.v1.6m2_pflotran.${case_name}.xml"

        # Check XML file
        if [ -f "$XML_FILE" ]; then
            echo "XML file found: $XML_FILE"
        else
            echo "ERROR: XML file not found: $XML_FILE"
            exit 1
        fi
        
        # Run ATS
        echo "Starting ATS simulation for $case_name"
        
	echo "JOBID=$SLURM_JOB_ID"
	echo "NODELIST=$SLURM_NODELIST"
	echo "NODES=$SLURM_JOB_NUM_NODES"
	echo "NTASKS=$SLURM_NTASKS"
	echo "CPUS_ON_NODE=$SLURM_CPUS_ON_NODE"
	scontrol show hostnames "$SLURM_NODELIST"
	#srun --ntasks=8 --cpus-per-task=1 --cpu-bind=cores \
        #     /compass/ber200003/xiao284/softwares/ats-master-251124/amanzi-install-master-Release/bin/ats \
        #     --xml_file="$XML_FILE" \
        #     > "${case_name}.out" 2> "${case_name}.err"
	srun --nodes=1 --ntasks=8 --cpus-per-task=1 \
     		--exclusive --distribution=block --hint=nomultithread \
     		--nodelist="$SLURM_NODELIST" \
     		/compass/ber200003/xiao284/softwares/ats-master-251124/amanzi-install-master-Release/bin/ats \
     		--xml_file="$XML_FILE" \
     		> "${case_name}.out" 2> "${case_name}.err"
        
	ats_exit_code=$?
	case_end_time=$(date +%s)
        case_elapsed=$((case_end_time - overall_start_time))

        # Count output files
        echo "Counting output files for $case_name"
        xmf_count=$(ls -1 ats_vis_surface_data.h5.*.xmf 2>/dev/null | wc -l)

	echo "$case_name total case time: $case_elapsed seconds ($(($case_elapsed / 60)) minutes)"
        echo "$case_name completed with exit code: $ats_exit_code"
	echo "$case_name generated $xmf_count XMF files and $h5_count H5 files"

	# Write timing summary to a separate file
        echo "=== TIMING SUMMARY FOR $case_name ===" >> "${case_name}_timing.log"
        echo "Case started: $(date -d @$overall_start_time)" >> "${case_name}_timing.log"
        echo "Case completed: $(date -d @$case_end_time)" >> "${case_name}_timing.log"
        echo "Total case time: $case_elapsed seconds ($(($case_elapsed / 60)) minutes)" >> "${case_name}_timing.log"
        echo "Exit code: $ats_exit_code" >> "${case_name}_timing.log"
	echo "=== OUTPUT FILES ===" >> "${case_name}_timing.log"
	echo "VIS_SURFACE XMF files generated: $xmf_count" >> "${case_name}_timing.log"
        
    ) &
    
    # Store the PID of the subshell
    PIDS[i]=$!
    echo "Started $case_name with PID: ${PIDS[i]}"
done

# Wait for all jobs to complete
echo "=== Waiting for all jobs to complete ==="
for i in {0..4}; do
    echo "Waiting for ${CASES[i]} (PID: ${PIDS[i]})"
    wait ${PIDS[i]}
    exit_status=$?
    echo "${CASES[i]} finished with exit status: $exit_status"
done

echo "=== All cases completed! ==="

