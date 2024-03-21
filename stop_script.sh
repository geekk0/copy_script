#!/bin/bash

# Function to close screen sessions with a specific prefix
close_screen_sessions() {
    local prefix="$1"
    screen -ls | grep -oP '^\s*\K[^\s]+(?=.*Detached)' | while read -r session_name; do
        echo "Closing screen session: $session_name"
        screen -S "$session_name" -X quit
    done
    sudo screen -wipe >/dev/null 2>&1
}

# Close all screen sessions with the specified prefix
close_screen_sessions "copier_"

# Clean up any dead or lingering screen sessions
sudo screen -wipe >/dev/null 2>&1