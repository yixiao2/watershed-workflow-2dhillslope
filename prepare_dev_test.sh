#!/bin/bash
set -euo pipefail

# A fresh destination avoids overwriting an existing, possibly running case.
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target_dir=${1:-"$repo_dir/../test_Naches_ATS_2D_cleaned"}
mkdir -- "$target_dir"
mkdir -- "$target_dir/notebooks"
cp -- "$repo_dir"/notebooks/*.ipynb "$repo_dir"/notebooks/*.py \
    "$repo_dir/notebooks/config.json" "$repo_dir/notebooks/README.md" \
    "$repo_dir"/notebooks/caseflow-*-template.ats1.5.xml "$target_dir/notebooks/"
# Preserve external-data symlinks instead of copying raw datasets.
cp -d -- "$repo_dir/notebooks/data" "$repo_dir/notebooks/MODIS_raw" "$target_dir/notebooks/"
cp -a -- "$repo_dir/notebooks/ELM_outputs_process" "$repo_dir/notebooks/site_selection" "$target_dir/notebooks/"
cp -a -- "$repo_dir/caseflow-run0" "$repo_dir/caseflow-run1" "$repo_dir/caseflow-run2" \
    "$repo_dir/atspflotranutils" "$target_dir/"
# Notebooks 2–5 generate the lambda run directories from approved inputs.
