#!/bin/bash

# Define directories for the three steps
STEP1_DIR="caseflow-run0/NF01"
STEP2_DIR="caseflow-run1/NF01"
STEP3_DIR="casecybernetic-run1-365d/NF01"

# Function to get the creation time from the first and last file
function get_time_difference() {
  DIR=$1
  if [ -d "$DIR" ]; then
    # Get the creation time of the first and last file (sorted by creation time)
    FIRST_FILE_TIME=$(ls -lt --full-time --time=birth "$DIR" 2>/dev/null | tail -n 1 | awk '{print $6, $7, $8}')
    #LAST_FILE_TIME=$(ls -lt --time=birth "$DIR" 2>/dev/null | head -n 1 | awk '{print $6, $7, $8}')
    LAST_FILE_TIME=$(ls -lt --full-time --time=birth "$DIR" 2>/dev/null | grep -v '^total' | head -n 1 | awk '{print $6, $7, $8}')
    
    # Convert to epoch for time difference calculation
    FIRST_EPOCH=$(date -d "$FIRST_FILE_TIME" +%s 2>/dev/null)
    LAST_EPOCH=$(date -d "$LAST_FILE_TIME" +%s 2>/dev/null)
    
    # Calculate time difference if values are valid
    if [ -n "$FIRST_EPOCH" ] && [ -n "$LAST_EPOCH" ]; then
      TIME_DIFF=$((LAST_EPOCH - FIRST_EPOCH))
      echo $TIME_DIFF
    else
      echo "Error calculating time for $DIR"
    fi
  else
    echo "Directory $DIR does not exist"
  fi
}

# Function to format time in minutes or hours
function format_time() {
  TIME=$1
  UNIT=$2
  if [ "$UNIT" == "minutes" ]; then
    echo "$(bc <<< "scale=2; $TIME / 60") min"
  elif [ "$UNIT" == "hours" ]; then
    echo "$(bc <<< "scale=2; $TIME / 3600") hr"
  else
    echo "$TIME s"
  fi
}

# Estimate running times
STEP1_TIME=$(get_time_difference "$STEP1_DIR")
STEP2_TIME=$(get_time_difference "$STEP2_DIR")
STEP3_TIME=$(get_time_difference "$STEP3_DIR")

# Format and display the results
if [[ "$STEP1_TIME" =~ ^[0-9]+$ ]]; then
  FORMATTED_STEP1_TIME=$(format_time "$STEP1_TIME" "minutes")
  echo "Running time for Step 1: $FORMATTED_STEP1_TIME"
else
  echo "Error calculating running time for Step 1"
fi

if [[ "$STEP2_TIME" =~ ^[0-9]+$ ]]; then
  FORMATTED_STEP2_TIME=$(format_time "$STEP2_TIME" "minutes")
  echo "Running time for Step 2: $FORMATTED_STEP2_TIME"
else
  echo "Error calculating running time for Step 2"
fi

if [[ "$STEP3_TIME" =~ ^[0-9]+$ ]]; then
  FORMATTED_STEP3_TIME=$(format_time "$STEP3_TIME" "hours")
  echo "Running time for Step 3: $FORMATTED_STEP3_TIME"
else
  echo "Error calculating running time for Step 3"
fi

# Total simulation time calculation (optional)
if [[ "$STEP1_TIME" =~ ^[0-9]+$ ]] && [[ "$STEP2_TIME" =~ ^[0-9]+$ ]] && [[ "$STEP3_TIME" =~ ^[0-9]+$ ]]; then
  TOTAL_TIME=$((STEP1_TIME + STEP2_TIME + STEP3_TIME))
  FORMATTED_TOTAL_TIME=$(format_time "$TOTAL_TIME" "seconds")
  echo "Total simulation time: $FORMATTED_TOTAL_TIME"
else
  echo "Error: Unable to calculate total simulation time."
fi
