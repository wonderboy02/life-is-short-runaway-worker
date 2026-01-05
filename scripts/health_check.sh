#!/bin/bash

# Check if worker process is running
if ! pgrep -f "worker.py" > /dev/null; then
    echo "Worker process not found"
    exit 1
fi

# Check if log file exists and is recent
LOG_FILE=$(ls -t logs/*.log 2>/dev/null | head -1)
if [ -z "$LOG_FILE" ]; then
    echo "No log file found"
    exit 1
fi

# Check if log file was modified in the last 5 minutes
if [ $(find "$LOG_FILE" -mmin -5 | wc -l) -eq 0 ]; then
    echo "Worker seems stuck (no recent logs)"
    exit 1
fi

echo "Worker healthy"
exit 0
