#!/bin/bash

# Get the current directory
SCRIPT_DIR=$(pwd)

# Find all config files in the current directory
CONFIG_FILES=$(find "$SCRIPT_DIR" -maxdepth 1 -type f -iname "*_config.ini")

# Function to run the copier subprocess
run_copier_subprocess() {
    local config_file="$1"
    local filename=$(basename "$config_file")
    local screen_name="copier_${filename%_config.ini}"

    # Create a new screen session with the name of the config file
    screen -dmS "$screen_name" bash -c "source /cloud/copy_script/cs_env/bin/activate && python3 /cloud/copy_script/photos_copy_script.py '$config_file'"
}

# Iterate over config files and run the copier subprocess for each one
for config_file in $CONFIG_FILES; do
    run_copier_subprocess "$config_file"
done
