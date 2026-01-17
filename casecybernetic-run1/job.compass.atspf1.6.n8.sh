#!/bin/bash
#SBATCH --account=ber200003
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --job-name=run1-9yr
#SBATCH --time=48:00:00

source /etc/profile.d/modules.sh
module purge
source ~/set_ats_env/ats-master.compass.251124.sh

echo "=== Job started at: $(date) ==="
echo "Running on host(s): $(hostname)"
echo "Working directory (submit): $(pwd)"

overall_start_time=$(date +%s)

# ---- Setup run directory ----
DIR_NAME="NF01"
DATE=$(date +%y%m%d%H%M%S)

if [ -d "$DIR_NAME" ]; then
    if [ -z "$(ls -A "$DIR_NAME")" ]; then
        echo "Directory '$DIR_NAME' exists and is empty."
    else
        echo "Directory '$DIR_NAME' exists and is not empty. Renaming to '${DIR_NAME}.${DATE}'"
        mv "$DIR_NAME" "${DIR_NAME}.${DATE}"
        mkdir "$DIR_NAME"
        echo "Created new empty directory '$DIR_NAME'."
    fi
else
    echo "Directory '$DIR_NAME' does not exist. Creating it."
    mkdir "$DIR_NAME"
fi

cd "$DIR_NAME" || { echo "Failed to cd to '$DIR_NAME'"; exit 1; }
echo "Now in: $(pwd)"

# ---- XML ----
XML_FILE="../NF01_nx100_nz18.run1.v1.6m2_pflotran.fixed1000s.xml"
if [ -f "$XML_FILE" ]; then
    echo "XML file found: $XML_FILE"
else
    echo "ERROR: XML file not found: $XML_FILE"
    exit 1
fi

# ---- Run ATS ----
echo "Starting ATS simulation..."
srun --ntasks=8 --cpus-per-task=1 --cpu-bind=cores \
     /compass/ber200003/xiao284/softwares/ats-master-251124/amanzi-install-master-Release/bin/ats \
     --xml_file="$XML_FILE" \
     > ats.out 2> ats.err

ats_exit_code=$?
end_time=$(date +%s)
elapsed=$((end_time - overall_start_time))

# ---- Count output files (customize patterns if needed) ----
xmf_count=$(ls -1 ats_vis_surface_data.h5.*.xmf 2>/dev/null | wc -l)
h5_count=$(ls -1 *.h5 2>/dev/null | wc -l)

echo "ATS finished with exit code: $ats_exit_code"
echo "Total run time: $elapsed seconds ($(($elapsed/60)) minutes)"
echo "Generated $xmf_count XMF files"
echo "Generated $h5_count H5 files"

# ---- Timing summary log ----
TIMING_LOG="timing_summary.log"
{
    echo "=== TIMING SUMMARY ==="
    echo "Directory: $(pwd)"
    echo "Job started:   $(date -d @"$overall_start_time")"
    echo "Job completed: $(date -d @"$end_time")"
    echo "Total time: $elapsed seconds ($(($elapsed/60)) minutes)"
    echo "Exit code: $ats_exit_code"
    echo "=== OUTPUT FILES ==="
    echo "VIS_SURFACE XMF files: $xmf_count"
    echo "H5 files: $h5_count"
} >> "$TIMING_LOG"

echo "=== Job completed at: $(date) ==="
exit $ats_exit_code
