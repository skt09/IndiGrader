#!/bin/bash
# ==============================================================================
# IndiGrader Graceful Shutdown Script
# ==============================================================================

echo "[*] Initiating graceful shutdown of IndiGrader..."

# 1. Stop FastAPI to prevent new submissions
echo "[*] Stopping FastAPI Server..."
pkill -f "fastapi run main.py" || pkill -f "uvicorn main:app"
echo "[+] FastAPI stopped. No new submissions will be accepted."

# 2. Wait for Celery queue to drain
echo "[*] Waiting for Celery to process all pending submissions..."
while true; do
    # Check the length of the default 'celery' queue in Redis
    QUEUE_LEN=$(redis-cli llen celery 2>/dev/null)
    
    # If redis-cli fails or returns empty, assume 0 or error
    if [ -z "$QUEUE_LEN" ]; then
        QUEUE_LEN=0
    fi

    if [ "$QUEUE_LEN" -eq 0 ]; then
        echo -e "\n[+] Redis queue is empty! All pending submissions have been processed."
        break
    else
        echo -ne "\r[*] Submissions waiting in queue: $QUEUE_LEN (Waiting...)"
        sleep 2
    fi
done

# 3. Gracefully stop Celery workers (finishes currently executing tasks)
echo "[*] Sending graceful shutdown signal to Celery workers..."
pkill -15 -f "celery -A task.capp worker"
echo "[*] Waiting for Celery to wrap up active grading..."
while pgrep -f "celery -A task.capp worker" > /dev/null; do
    sleep 1
done
echo "[+] Celery workers stopped."

# 4. Stop Redis (Optional, comment out if Redis is used by other apps on this server)
# echo "4️⃣  Stopping Redis server..."
# sudo systemctl stop redis-server
# echo "✅ Redis stopped."

echo "[+] Shutdown Complete! It is now safe to zip this folder and take it back."
