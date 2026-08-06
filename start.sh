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
if ! command -v celery &> /dev/null; then
    echo -e "\033[0;31m[-] ERROR: 'celery' command not found. Please activate your virtual environment or install celery.\033[0m"
    exit 1
fi

if ! command -v fastapi &> /dev/null; then
    echo -e "\033[0;31m[-] ERROR: 'fastapi' command not found. Please activate your virtual environment or install fastapi.\033[0m"
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

PORT=$(jq -r '.port // 8000' config.json 2>/dev/null || echo 8000)
QUEUE_NAME=$(jq -r '.queue_name // "celery"' config.json 2>/dev/null || echo "celery")
CELERY_WORKERS=${CELERY_WORKERS:-12}

# 2. Start Celery Worker in the background
echo -e "\033[1;32m[+] Starting Celery Worker (queue: $QUEUE_NAME, concurrency: $CELERY_WORKERS)...\033[0m"
celery -A task.capp worker -Q "$QUEUE_NAME" --concurrency "$CELERY_WORKERS" --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > logs/celery.pid
echo -e "\033[1;30m   (Celery logs available at: logs/celery.log)\033[0m"

# 3. Start FastAPI Server in the background
echo -e "\033[1;32m[+] Starting FastAPI Server on port $PORT...\033[0m"
fastapi run main.py --port "$PORT" > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo $FASTAPI_PID > logs/fastapi.pid
echo -e "\033[1;30m   (FastAPI logs available at: logs/fastapi.log)\033[0m"

# 4. Verify processes started successfully
sleep 2
FAILED=0
if ! kill -0 "$CELERY_PID" 2>/dev/null; then
    echo -e "\033[0;31m[-] ERROR: Celery worker failed to start. Check logs/celery.log:\033[0m"
    tail -n 10 logs/celery.log 2>/dev/null
    rm -f logs/celery.pid
    FAILED=1
fi

if ! kill -0 "$FASTAPI_PID" 2>/dev/null; then
    echo -e "\033[0;31m[-] ERROR: FastAPI server failed to start. Check logs/fastapi.log:\033[0m"
    tail -n 10 logs/fastapi.log 2>/dev/null
    rm -f logs/fastapi.pid
    FAILED=1
fi

if [ "$FAILED" -eq 1 ]; then
    echo -e "\033[0;31m[-] Startup failed due to errors above.\033[0m"
    exit 1
fi

echo -e "\033[1;32m[+] All services started successfully!\033[0m"
echo -e "\033[1;36m------------------------------------------------------\033[0m"
echo -e "\033[1;36m[*] To monitor the server, run: tail -f logs/fastapi.log\033[0m"
echo -e "\033[1;36m[*] To monitor grading, run:    tail -f logs/celery.log\033[0m"
echo -e "\033[1;33m[-] To stop safely, run:        ./stop.sh\033[0m"
echo -e "\033[1;36m------------------------------------------------------\033[0m"
