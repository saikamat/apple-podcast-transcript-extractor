#!/bin/bash

# Start both processes
echo "Starting Podcast Transcript Extractor..."

# Start monitor in background
python monitor_ttml.py > monitor.log 2>&1 &
MONITOR_PID=$!
echo "Monitor started with PID: $MONITOR_PID"

# Start web app in background
python app.py > webapp.log 2>&1 &
WEBAPP_PID=$!
echo "Web app started with PID: $WEBAPP_PID"

echo "================================================"
echo "Podcast Transcript Extractor running!"
echo "Web interface available at: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop all processes"
echo "================================================"

# Function to kill processes on exit
cleanup() {
    echo "Shutting down..."
    kill $MONITOR_PID
    kill $WEBAPP_PID
    exit 0
}

# Register the cleanup function for when script receives SIGINT
trap cleanup SIGINT

# Keep script running
while true; do
    sleep 1
done