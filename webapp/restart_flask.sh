#!/bin/bash

# Define the Python script path
APP_PATH="/home/pi/webapp/app.py"
LOG_FILE="/home/pi/webapp/logs/webui.log"

# Kill any existing Flask app process
echo "Stopping Flask app..."
pkill -f /home/pi/webapp/app.py

# Add a brief pause to ensure the process is fully terminated
sleep 2

# Restart the Flask app
echo "Starting Flask app..."
nohup python3 /home/pi/webapp/app.py > /home/pi/webapp/logs/webui.log 2>&1 &

echo "Flask app restarted."
