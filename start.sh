#!/bin/bash
# ==============================================================================
# IndiGrader Startup Script
# ==============================================================================

echo "[*] Starting IndiGrader Server..."

# Pre-flight Checks
echo "[*] Running pre-flight checks..."
if ! jq empty config.json 2>/dev/null; then
    echo "[-] ERROR: config.json is missing or contains invalid JSON."
    exit 1
fi

if ! ls statics/*.zip 1> /dev/null 2>&1; then
    echo "[-] ERROR: No starter kit .zip file found in statics/ folder."
    exit 1
fi
echo "[+] Pre-flight checks passed."

# Create logs directory if it doesn't exist
mkdir -p logs

# 1. Start Redis if not already running (Assumes Redis is installed as a system service or available in path)
if ! pgrep -x "redis-server" > /dev/null; then
    echo "[+] Starting Redis Server..."
    # You may need sudo depending on the lab machine setup, 
    # but normally we assume redis-server is available as a background service.
    # If running locally without systemd:
    redis-server --daemonize yes
else
    echo "[*] Redis is already running."
fi

# 2. Start Celery Worker in the background
echo "[+] Starting Celery Worker..."
celery -A task.capp worker --loglevel=info > logs/celery.log 2>&1 &
echo "   (Celery logs available at: logs/celery.log)"

# 3. Start FastAPI Server in the background
echo "[+] Starting FastAPI Server..."
fastapi run main.py > logs/fastapi.log 2>&1 &
echo "   (FastAPI logs available at: logs/fastapi.log)"

echo "[+] All services started successfully!"
echo "------------------------------------------------------"
echo "[*] To monitor the server, run: tail -f logs/fastapi.log"
echo "[*] To monitor grading, run:    tail -f logs/celery.log"
echo "[-] To stop safely, run:        ./stop.sh"
echo "------------------------------------------------------"
