#!/bin/bash
#SBATCH --account=ber200003
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --job-name=ats-kdeg
#SBATCH --time=48:00:00

source /etc/profile.d/modules.sh
module purge
source ~/set_ats_env/ats-1.5.2.compass.250212.sh

# Simplified approach - no function, direct execution
echo "Original directory: $(pwd)"

# Arrays to store background job PIDs
declare -a PIDS=()
declare -a CASES=("case_s1" "case_s2" "case_s3" "case_s4")
declare -a DIRS=("casecybernetic-run1.s1" "casecybernetic-run1.s2" "casecybernetic-run1.s3" "casecybernetic-run1.s4")

ORIGINAL_DIR=$(pwd)

# Record overall start time
overall_start_time=$(date +%s)
echo "=== Overall job started at: $(date) ==="

# Launch all cases
for i in {0..3}; do
    case_name=${CASES[i]}
    case_dir=${DIRS[i]}
    
    echo "=== Launching ${case_name} ==="
    
    # Use subshell to isolate each case
    (
        cd "$ORIGINAL_DIR/$case_dir"
        echo "Working in: $(pwd)"
        
        # Setup NF01 directory
        DIR_NAME="NF01"
        DATE=$(date +%y%m%d)
        
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
        
        # Check XML file
        if [ -f "../NF01_nx100_nz18.run1.vphong_pflotran.xml" ]; then
            echo "XML file found"
        else
            echo "ERROR: XML file not found"
            exit 1
        fi
        
        # Run ATS
        echo "Starting ATS simulation for $case_name"
        srun --ntasks=8 --cpus-per-task=1 --cpu-bind=cores \
             /compass/ber200003/xiao284/softwares/ats-152-250212/amanzi-install-ats-1.5-Release/bin/ats \
             --xml_file=../NF01_nx100_nz18.run1.vphong_pflotran.xml \
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
for i in {0..3}; do
    echo "Waiting for ${CASES[i]} (PID: ${PIDS[i]})"
    wait ${PIDS[i]}
    exit_status=$?
    echo "${CASES[i]} finished with exit status: $exit_status"
done

echo "=== All cases completed! ==="

