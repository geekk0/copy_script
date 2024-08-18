#!/bin/bash

# Validate input arguments
if [ $# -ne 4 ]; then
    echo "Usage: $0 <screen_session_name> <sudo_password> <config_file_name> <folder_path>"
    exit 1
fi

# Set input arguments
screen_session_name="$1"
sudo_password="$2"
config_file_name="$3"
folder_path="$4"

# screen -dmS "$screen_session_name" bash -c "source /cloud/copy_script/cs_env/bin/activate && ls -l"
screen -dmS "$screen_session_name" bash -c "source /cloud/copy_script/cs_env/bin/activate &&
    python3 /cloud/copy_script/enhance_folder.py '$config_file_name' '$folder_path' > output.log 2>&1"


