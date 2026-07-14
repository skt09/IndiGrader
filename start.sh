#!/bin/bash
# ==============================================================================
# IndiGrader Startup Script
# ==============================================================================

echo -e "\033[1;36m[*] Starting IndiGrader Server...\033[0m"

# Pre-flight Checks
echo -e "\033[1;34m[*] Running pre-flight checks...\033[0m"
if ! jq empty config.json 2>/dev/null; then
    echo -e "\033[0;31m[-] ERROR: config.json is missing or contains invalid JSON.\033[0m"
    exit 1
fi

if ! ls statics/*.zip 1> /dev/null 2>&1; then
    echo -e "\033[0;31m[-] ERROR: No starter kit .zip file found in statics/ folder.\033[0m"
    exit 1
fi
echo -e "\033[1;32m[+] Pre-flight checks passed.\033[0m"

# Create logs directory if it doesn't exist
mkdir -p logs

# 1. Start Redis if not already running (Assumes Redis is installed as a system service or available in path)
if ! pgrep -x "redis-server" > /dev/null; then
    echo -e "\033[1;32m[+] Starting Redis Server...\033[0m"
    # You may need sudo depending on the lab machine setup, 
    # but normally we assume redis-server is available as a background service.
    # If running locally without systemd:
    redis-server --daemonize yes
else
    echo -e "\033[1;33m[*] Redis is already running.\033[0m"
fi

# 2. Start Celery Worker in the background
echo -e "\033[1;32m[+] Starting Celery Worker...\033[0m"
celery -A task.capp worker --loglevel=info > logs/celery.log 2>&1 &
echo -e "\033[1;30m   (Celery logs available at: logs/celery.log)\033[0m"

# 3. Start FastAPI Server in the background
echo -e "\033[1;32m[+] Starting FastAPI Server...\033[0m"
fastapi run main.py > logs/fastapi.log 2>&1 &
echo -e "\033[1;30m   (FastAPI logs available at: logs/fastapi.log)\033[0m"

echo -e "\033[1;32m[+] All services started successfully!\033[0m"
echo -e "\033[1;36m------------------------------------------------------\033[0m"
echo -e "\033[1;36m[*] To monitor the server, run: tail -f logs/fastapi.log\033[0m"
echo -e "\033[1;36m[*] To monitor grading, run:    tail -f logs/celery.log\033[0m"
echo -e "\033[1;33m[-] To stop safely, run:        ./stop.sh\033[0m"
echo -e "\033[1;36m------------------------------------------------------\033[0m"
