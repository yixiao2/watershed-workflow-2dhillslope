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

# =============================================================================
# CONFIGURATION — edit these parallel arrays to match your cases
# =============================================================================
declare -a CASES=("IG01"    "UB01"    "LS01"    "MS01"    "HS01")
declare -a CASES_DIRS=("test_Naches_ATS_2D_cleaned.IG01" \
                       "test_Naches_ATS_2D_cleaned.UB01" \
                       "test_Naches_ATS_2D_cleaned.LS01" \
                       "test_Naches_ATS_2D_cleaned.MS01" \
                       "test_Naches_ATS_2D_cleaned.HS01")
# caseflow-run0
declare -a ATS_DIRS= ("caseflow-run0" \
                      "caseflow-run0" \
                      "caseflow-run0" \
                      "caseflow-run0" \
                      "caseflow-run0")
declare -a DIR_NAMES=("IG01"    "UB01"    "LS01"    "MS01"    "HS01")
declare -a XML_FILES=("IG01_nx100_nz18.run0.v1.6.xml" \
                      "UB01_nx100_nz18.run0.v1.6.xml" \
                      "LS01_nx100_nz18.run0.v1.6.xml" \
                      "MS01_nx100_nz18.run0.v1.6.xml" \
                      "HS01_nx100_nz18.run0.v1.6.xml")
# =============================================================================

NUM_CASES=${#CASES[@]}
ORIGINAL_DIR=$(pwd)

# Validate that all arrays have the same length
for arr_name in CASES_DIRS ATS_DIRS DIR_NAMES XML_FILES; do
    declare -n arr="$arr_name"
    if [ "${#arr[@]}" -ne "$NUM_CASES" ]; then
        echo "ERROR: Array $arr_name has ${#arr[@]} elements, expected $NUM_CASES"
        exit 1
    fi
done

# Print configuration summary
echo ""
echo "=== CONFIGURATION SUMMARY ==="
for ((i=0; i<NUM_CASES; i++)); do
    echo "  ${CASES[i]}:"
    echo "    CASES_DIRS : ${CASES_DIRS[i]}"
    echo "    ATS_DIRS   : ${ATS_DIRS[i]}"
    echo "    DIR_NAME   : ${DIR_NAMES[i]}"
    echo "    XML_FILES  : ${XML_FILES[i]}"
done
echo ""

# Record overall start time
overall_start_time=$(date +%s)
echo "=== Overall job started at: $(date) ==="

# Launch all cases
for ((i=0; i<NUM_CASES; i++)); do
    case_name=${CASES[i]}
    case_dir=${CASES_DIRS[i]}
    ats_dir =${ATS_DIRS[i]}
    dir_name=${DIR_NAMES[i]}
    xml_file=${XML_FILES[i]}

    echo "=== Launching ${case_name} ==="

    # Use subshell to isolate each case
    (
        cd "$ORIGINAL_DIR/$case_dir/$ats_dir"
        echo "Working in: $(pwd)"

        # Setup output directory
        DATE=$(date +%y%m%d)

        if [ -d "$dir_name" ]; then
            if [ ! -z "$(ls -A "$dir_name")" ]; then
                echo "Renaming existing directory to ${dir_name}.${DATE}"
                mv "$dir_name" "${dir_name}.${DATE}"
                mkdir "$dir_name"
            else
                echo "Directory $dir_name exists and is empty"
            fi
        else
            echo "Creating directory $dir_name"
            mkdir "$dir_name"
        fi

        cd "$dir_name"
        echo "Now in: $(pwd)"

        # Check XML file
        if [ -f "../${xml_file}" ]; then
            echo "XML file found: ${xml_file}"
        else
            echo "ERROR: XML file not found: ../${xml_file}"
            exit 1
        fi

        # Run ATS
        echo "Starting ATS simulation for $case_name"
        srun --ntasks=8 --cpus-per-task=1 --cpu-bind=cores \
             /compass/ber200003/xiao284/softwares/ats-152-250212/amanzi-install-ats-1.5-Release/bin/ats \
             --xml_file=../"${xml_file}" \
             > "${case_name}.out" 2> "${case_name}.err"

        ats_exit_code=$?
        case_end_time=$(date +%s)
        case_elapsed=$((case_end_time - overall_start_time))

        # Count output files
        echo "Counting output files for $case_name"
        xmf_count=$(ls -1 ats_vis_surface_data.h5.*.xmf 2>/dev/null | wc -l)

        echo "$case_name total case time: $case_elapsed seconds ($(($case_elapsed / 60)) minutes)"
        echo "$case_name completed with exit code: $ats_exit_code"
        echo "$case_name generated $xmf_count XMF files"

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
for ((i=0; i<NUM_CASES; i++)); do
    echo "Waiting for ${CASES[i]} (PID: ${PIDS[i]})"
    wait ${PIDS[i]}
    exit_status=$?
    echo "${CASES[i]} finished with exit status: $exit_status"
done

echo "=== All cases completed! ==="