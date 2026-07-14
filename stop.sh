#!/bin/bash
# ==============================================================================
# IndiGrader Graceful Shutdown Script
# ==============================================================================

echo -e "\033[1;36m[*] Initiating graceful shutdown of IndiGrader...\033[0m"

# 1. Stop FastAPI to prevent new submissions
echo -e "\033[1;34m[*] Stopping FastAPI Server...\033[0m"
pkill -f "fastapi run main.py" || pkill -f "uvicorn main:app"
echo -e "\033[1;32m[+] FastAPI stopped. No new submissions will be accepted.\033[0m"

# 2. Wait for Celery queue to drain
echo -e "\033[1;33m[*] Waiting for Celery to process all pending submissions...\033[0m"
while true; do
    # Check the length of the default 'celery' queue in Redis
    QUEUE_LEN=$(redis-cli llen celery 2>/dev/null)
    
    # If redis-cli fails or returns empty, assume 0 or error
    if [ -z "$QUEUE_LEN" ]; then
        QUEUE_LEN=0
    fi

    if [ "$QUEUE_LEN" -eq 0 ]; then
        echo -e "\n\033[1;32m[+] Redis queue is empty! All pending submissions have been processed.\033[0m"
        break
    else
        echo -ne "\r\033[1;33m[*] Submissions waiting in queue: $QUEUE_LEN (Waiting...)\033[0m"
        sleep 2
    fi
done

# 3. Gracefully stop Celery workers (finishes currently executing tasks)
echo -e "\033[1;34m[*] Sending graceful shutdown signal to Celery workers...\033[0m"
pkill -15 -f "celery -A task.capp worker"
echo -e "\033[1;33m[*] Waiting for Celery to wrap up active grading...\033[0m"
while pgrep -f "celery -A task.capp worker" > /dev/null; do
    sleep 1
done
echo -e "\033[1;32m[+] Celery workers stopped.\033[0m"

# 4. Stop Redis (Optional, comment out if Redis is used by other apps on this server)
# echo "4️⃣  Stopping Redis server..."
# sudo systemctl stop redis-server
# echo "✅ Redis stopped."

echo -e "\033[1;32m[+] Shutdown Complete! It is now safe to zip this folder and take it back.\033[0m"
