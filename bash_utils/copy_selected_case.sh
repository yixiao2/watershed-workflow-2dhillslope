#!/bin/bash

# =============================================================================
# Script: copy_selected.sh
# Description: Copy selected subfolders and files from source to destination.
# Usage: ./copy_selected.sh <source_folder> <destination_folder>
# =============================================================================

set -e

# ---------------------
# Validate input arguments
# ---------------------
if [ "$#" -ne 2 ]; then
    echo "ERROR: Exactly 2 arguments required."
    echo "Usage: $0 <source_folder> <destination_folder>"
    exit 1
fi

SRC="$1"
DST="$2"

# ---------------------
# Check source exists
# ---------------------
if [ ! -d "$SRC" ]; then
    echo "ERROR: Source folder does not exist: $SRC"
    exit 1
fi

# ---------------------
# Handle destination folder
# ---------------------
if [ -d "$DST" ]; then
    # Destination exists — check if it's empty
    if [ "$(ls -A "$DST")" ]; then
        echo "ERROR: Destination folder exists and is NOT empty: $DST"
        echo "       Please provide an empty or non-existing destination folder."
        exit 1
    else
        echo "Destination folder exists and is empty. Proceeding..."
    fi
else
    echo "Destination folder does not exist. Creating: $DST"
    mkdir -p "$DST"
fi

# ---------------------
# Define items to copy
# ---------------------
SUBDIRS=(
    "caseflow-run0"
    "caseflow-run1"
    "caseflow-run2"
    "casecybernetic-run1.s1"
    "casecybernetic-run2.s1"
    "data-processed"
)

FILES=(
    "notebooks/config.json"
)

# ---------------------
# Copy subfolders
# ---------------------
for dir in "${SUBDIRS[@]}"; do
    SRC_PATH="$SRC/$dir"
    if [ -d "$SRC_PATH" ]; then
        echo "Copying subfolder: $dir"
        cp -r "$SRC_PATH" "$DST/"
    else
        echo "WARNING: Subfolder not found, skipping: $SRC_PATH"
    fi
done

# ---------------------
# Copy files
# ---------------------
for file in "${FILES[@]}"; do
    SRC_PATH="$SRC/$file"
    if [ -f "$SRC_PATH" ]; then
        # Recreate the parent directory structure in destination
        FILE_DIR="$(dirname "$file")"
        mkdir -p "$DST/$FILE_DIR"
        echo "Copying file: $file"
        cp "$SRC_PATH" "$DST/$file"
    else
        echo "WARNING: File not found, skipping: $SRC_PATH"
    fi
done

echo ""
echo "===== Copy complete! ====="
echo "Destination: $DST"
echo ""
echo "Contents:"
ls -la "$DST"
