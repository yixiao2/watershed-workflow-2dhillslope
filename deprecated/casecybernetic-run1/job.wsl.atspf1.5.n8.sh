#!/bin/bash
#source ~/set_ww_env/ww-1.5.wsl.25feb.sh

# Define the directory name
DIR_NAME="NF01"

# Get the current date in YYMMDD format
DATE=$(date +%y%m%d)

# Check if the directory exists
if [ -d "$DIR_NAME" ]; then
    # Check if the directory is empty
    if [ -z "$(ls -A "$DIR_NAME")" ]; then
        echo "Directory '$DIR_NAME' exists and is empty. No need to rename or recreate it."
    else
        echo "Directory '$DIR_NAME' already exists and is not empty. Renaming it to '${DIR_NAME}.${DATE}'."
        cp -r "$DIR_NAME" "${DIR_NAME}.${DATE}"
        rm -rf "$DIR_NAME"
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
mpiexec -n 8 ats --xml_file=../NF01_nx100_nz18.run1.v1.5_pflotran.testwsl.xml >> run1.output

