#!/bin/bash
# ==============================================================================
# IndiGrader Graceful Shutdown Script
# ==============================================================================

echo -e "\033[1;36m[*] Initiating graceful shutdown of IndiGrader...\033[0m"

PORT=$(jq -r '.port // 8000' config.json 2>/dev/null || echo 8000)
QUEUE_NAME=$(jq -r '.queue_name // "celery"' config.json 2>/dev/null || echo "celery")

# 1. Stop FastAPI to prevent new submissions
echo -e "\033[1;34m[*] Stopping FastAPI Server (port: $PORT)...\033[0m"
if [ -f logs/fastapi.pid ]; then
    FASTAPI_PID=$(cat logs/fastapi.pid 2>/dev/null)
    if [ -n "$FASTAPI_PID" ] && kill -0 "$FASTAPI_PID" 2>/dev/null; then
        kill "$FASTAPI_PID" 2>/dev/null
    fi
    rm -f logs/fastapi.pid
else
    pkill -f "port $PORT" 2>/dev/null || pkill -f "port=$PORT" 2>/dev/null
fi
echo -e "\033[1;32m[+] FastAPI stopped. No new submissions will be accepted.\033[0m"

# 2. Wait for Celery queue to drain
echo -e "\033[1;33m[*] Waiting for Celery queue ($QUEUE_NAME) to process all pending submissions...\033[0m"
while true; do
    QUEUE_LEN=$(redis-cli llen "$QUEUE_NAME" 2>/dev/null)
    
    if [ -z "$QUEUE_LEN" ]; then
        QUEUE_LEN=0
    fi

    if [ "$QUEUE_LEN" -eq 0 ]; then
        echo -e "\n\033[1;32m[+] Redis queue ($QUEUE_NAME) is empty! All pending submissions have been processed.\033[0m"
        break
    else
        echo -ne "\r\033[1;33m[*] Submissions waiting in queue ($QUEUE_NAME): $QUEUE_LEN (Waiting...)\033[0m"
        sleep 2
    fi
done

# 3. Gracefully stop Celery workers (finishes currently executing tasks)
echo -e "\033[1;34m[*] Sending graceful shutdown signal to Celery worker (queue: $QUEUE_NAME)...\033[0m"
CELERY_PID=""
if [ -f logs/celery.pid ]; then
    CELERY_PID=$(cat logs/celery.pid 2>/dev/null)
    if [ -n "$CELERY_PID" ] && kill -0 "$CELERY_PID" 2>/dev/null; then
        kill -15 "$CELERY_PID" 2>/dev/null
    fi
    rm -f logs/celery.pid
else
    pkill -15 -f "celery -A task.capp worker -Q $QUEUE_NAME" 2>/dev/null
fi

echo -e "\033[1;33m[*] Waiting for Celery to wrap up active grading...\033[0m"
if [ -n "$CELERY_PID" ]; then
    while kill -0 "$CELERY_PID" 2>/dev/null; do
        sleep 1
    done
else
    while pgrep -f "celery -A task.capp worker -Q $QUEUE_NAME" > /dev/null; do
        sleep 1
    done
fi
echo -e "\033[1;32m[+] Celery workers stopped.\033[0m"

# 4. Stop Redis (Optional, comment out if Redis is used by other apps on this server)
# echo "4️⃣  Stopping Redis server..."
# sudo systemctl stop redis-server
# echo "✅ Redis stopped."

echo -e "\033[1;32m[+] Shutdown Complete! It is now safe to zip this folder and take it back.\033[0m"
