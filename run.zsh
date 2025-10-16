#!/usr/bin/zsh

# Allow root to connect to X server
xhost +SI:localuser:root

# Run the command
sudo -E env PATH="$PATH" SUPABASE_CREDENTIALS="/home/ky/Projects/AEye/.venv/db.json" QT_QPA_PLATFORM="xcb" DISPLAY=:1 /home/ky/Projects/AEye/.venv/bin/python main.py

# Capture the exit code
EXIT_CODE=$?

# Revoke access (for security)
xhost -SI:localuser:root

# Exit with the same code as the Python script
exit $EXIT_CODE
