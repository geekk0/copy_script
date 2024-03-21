#!/bin/bash

# Function to run the copier subprocess
run_copier_subprocess() {
    local config_file="$1"
    local filename=$(basename "$config_file")
    local screen_name="copier_${filename%_config.ini}"

    # Create a new screen session with the name of the config file
    screen -dmS "$screen_name" bash -c "source /cloud/copy_script/cs_env/bin/activate &&
    python3 /cloud/copy_script/photos_copy_script.py '$config_file'"
}

started_processes=()

while true; do
    # Get the current directory
    SCRIPT_DIR=$(pwd)

    # Find all config files in the current directory
    CONFIG_FILES=$(find "$SCRIPT_DIR" -maxdepth 1 -type f -iname "*_config.ini")

    # Iterate over config files
    for config_file in $CONFIG_FILES; do
        # Extract the base name of the config file
        filename=$(basename "$config_file")
        # Generate the screen name
        screen_name="copier_${filename%_config.ini}"

        # Check if the subprocess is already running
        if [[ ! " ${started_processes[@]} " =~ " $screen_name " ]]; then
            # Start the subprocess
            run_copier_subprocess "$config_file"
            # Add the subprocess name to the list
            started_processes+=("$screen_name")
        fi
    done

    # Sleep for a period before checking again
    sleep 60  # Adjust as needed
done
