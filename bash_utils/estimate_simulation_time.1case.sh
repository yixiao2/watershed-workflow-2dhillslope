#!/bin/bash

# Function to display usage
function usage() {
  echo "Usage: $0 --dir=<directory_path>"
  echo "Example: $0 --dir=\"./casecybernetic-run1.s1/NF01\""
  exit 1
}

# Default pattern (can be overridden by command line argument)
FILE_PATTERN="ats_vis_surface_data.h5.*.xmf"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dir=*)
      TARGET_DIR="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option $1"
      usage
      ;;
  esac
done

# Check if directory argument is provided
if [ -z "$TARGET_DIR" ]; then
  echo "Error: Directory path is required"
  usage
fi

# Function to count files matching the pattern
function count_pattern_files() {
  DIR=$1
  PATTERN=$2

  if [ -d "$DIR" ]; then
    # Use find to count files matching the pattern
    FILE_COUNT=$(find "$DIR" -maxdepth 1 -name "$PATTERN" -type f 2>/dev/null | wc -l)
    echo $FILE_COUNT
  else
    echo "0"
  fi
}

# Function to get the creation time from the first and last file
function get_time_difference() {
  DIR=$1
  if [ -d "$DIR" ]; then
    # Check if directory has files
    FILE_COUNT=$(ls -1 "$DIR" 2>/dev/null | wc -l)
    if [ "$FILE_COUNT" -eq 0 ]; then
      echo "Directory is empty"
      return
    fi
    
    # Get the creation time of the first and last file (sorted by creation time)
    FIRST_FILE_TIME=$(ls -lt --full-time --time=birth "$DIR" 2>/dev/null | tail -n 1 | awk '{print $6, $7, $8}')
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

# Function to format time in appropriate units
function format_time() {
  TIME=$1
  
  if [ "$TIME" -lt 60 ]; then
    echo "${TIME}s"
  elif [ "$TIME" -lt 3600 ]; then
    echo "$(bc <<< "scale=2; $TIME / 60") min"
  else
    echo "$(bc <<< "scale=2; $TIME / 3600") hr"
  fi
}

# Function to format time with specific unit
function format_time_unit() {
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

echo "Analyzing directory: $TARGET_DIR"
echo "File pattern: $FILE_PATTERN"
echo "----------------------------------------"

# Count files matching the pattern
PATTERN_FILE_COUNT=$(count_pattern_files "$TARGET_DIR" "$FILE_PATTERN")

# Get running time for the specified directory
RUNNING_TIME=$(get_time_difference "$TARGET_DIR")

# Display the file count results
echo "File Analysis:"
echo "  - Files matching pattern '$FILE_PATTERN': $PATTERN_FILE_COUNT"
echo ""

# Display the results
if [[ "$RUNNING_TIME" =~ ^[0-9]+$ ]]; then
  # Auto-format based on duration
  FORMATTED_TIME=$(format_time "$RUNNING_TIME")
  
  echo "Running time: $FORMATTED_TIME"
  echo ""
  echo "Time breakdown:"
  echo "  - In seconds: ${RUNNING_TIME}s"
  echo "  - In minutes: $(format_time_unit "$RUNNING_TIME" "minutes")"
  echo "  - In hours: $(format_time_unit "$RUNNING_TIME" "hours")"
else
  echo "Error: $RUNNING_TIME"
  exit 1
fi

