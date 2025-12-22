#!/bin/bash

#SBATCH --account=ber200003
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8

#SBATCH --job-name=flow-run1
#SBATCH --time=12:00:00

source /etc/profile.d/modules.sh
module purge
source ~/set_ats_env/ats-master.compass.251124.sh

# Define the directory name
DIR_NAME="NF01"

# Get the current date in YYYY-MM-DD-HHMMSS format
DATE=$(date +%Y-%m-%d-%H%M%S)

# Check if the directory exists
if [ -d "$DIR_NAME" ]; then
    # Check if the directory is empty
    if [ -z "$(ls -A "$DIR_NAME")" ]; then
        echo "Directory '$DIR_NAME' exists and is empty. No need to rename or recreate it."
    else
        echo "Directory '$DIR_NAME' already exists and is not empty. Renaming it to '${DIR_NAME}.${DATE}'."
        mv "$DIR_NAME" "${DIR_NAME}.${DATE}"
        mkdir "$DIR_NAME"
        echo "Created a new empty directory '$DIR_NAME'."
    fi
else
    echo "Directory '$DIR_NAME' does not exist. Creating it."
    mkdir "$DIR_NAME"
    echo "Created directory '$DIR_NAME'."
fi

# Navigate into the directory
cd "$DIR_NAME" || { echo "Failed to change directory to '$DIR_NAME'. Exiting."; exit 1; }

# Execute the mpiexec command

srun -n 8 /compass/ber200003/xiao284/softwares/ats-master-251124/amanzi-install-master-Release/bin/ats --xml_file=../NF01_nx100_nz18.run1.v1.6.xml
