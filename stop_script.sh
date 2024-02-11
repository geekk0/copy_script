#!/bin/bash

# Function to close screen sessions with a specific prefix
close_screen_sessions() {
    local prefix="$1"
    screen -ls | grep -oP '^\s*\K[^\s]+(?=.*Detached)' | while read -r session_name; do
        echo "Closing screen session: $session_name"
        screen -S "$session_name" -X quit
    done
}

# Close all screen sessions with the specified prefix
close_screen_sessions "copier_"
