from task import handle_submission
from celery.result import AsyncResult
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi import FastAPI, UploadFile, Form, File, Request, HTTPException, status
from datetime import datetime
from contextlib import asynccontextmanager
import threading
import signal
import logging
import glob
import json
import csv
import asyncio
import os
DEBUG = False


logger = logging.getLogger(__name__)

# Globals
STUDENTS_FILE = "students.txt"
REGISTRATIONS_FILE = "registrations.csv"
VIOLATIONS_FILE = "violations.csv"
PWD_STUDENTS_FILE = "pwd_students.txt"
CONFIG_FILE = "config.json"
lab_config = {}
config_mtime_ns = None
config_lock = threading.RLock()
previous_sighup_handler = None
pwd_rolls = set()

student_list = set()
# fast lookups: { "ROLL_NO": "ip_address" }
ip_roll_map = {}

file_lock = asyncio.Lock()


def reload_config_if_changed(force=False, source="request"):
    """Reload config.json atomically when its on-disk version changes."""
    global lab_config, config_mtime_ns

    try:
        file_mtime_ns = os.stat(CONFIG_FILE).st_mtime_ns
    except OSError as exc:
        if force:
            logger.error("Unable to stat %s after %s: %s",
                         CONFIG_FILE, source, exc)
        return False

    with config_lock:
        if not force and file_mtime_ns == config_mtime_ns:
            return False

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                candidate_config = json.load(f)

            if not isinstance(candidate_config, dict):
                raise ValueError("top-level value must be a JSON object")

            candidate_config["start_time"] = datetime.fromisoformat(
                candidate_config["start_time"]
            )
            candidate_config["end_time"] = datetime.fromisoformat(
                candidate_config["end_time"]
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            config_mtime_ns = file_mtime_ns
            logger.error(
                "Keeping the previous valid configuration: %s could not be "
                "loaded after %s: %s",
                CONFIG_FILE,
                source,
                exc,
            )
            return False

        lab_config = candidate_config
        config_mtime_ns = file_mtime_ns
        logger.info(
            "Loaded updated %s after %s; end_time=%s",
            CONFIG_FILE,
            source,
            lab_config["end_time"].isoformat(),
        )
        return True


def handle_sighup(signum, frame):
    """Allow an administrator to force a config reload from the shell."""
    reload_config_if_changed(force=True, source="SIGHUP")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global previous_sighup_handler
    print("Application starting up...")

    print("Loading config.json...")
    if not reload_config_if_changed(force=True, source="startup"):
        raise RuntimeError(f"Unable to load a valid {CONFIG_FILE}")

    previous_sighup_handler = signal.getsignal(signal.SIGHUP)
    signal.signal(signal.SIGHUP, handle_sighup)

    print("Loading pwd_students.txt...")
    if os.path.exists(PWD_STUDENTS_FILE):
        with open(PWD_STUDENTS_FILE, mode='r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    pwd_rolls.add(line.strip())

    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, mode='r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    student_list.add(line.strip())

    if len(student_list) == 0:
        print("No student in the class. Exiting...")
        return

    if os.path.exists(REGISTRATIONS_FILE):
        with open(REGISTRATIONS_FILE, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                next(reader)  # Skip header
            except StopIteration:
                pass  # File is empty

            for row in reader:
                if row and len(row) == 2:
                    roll_no, ip_address = row
                    ip_roll_map[roll_no] = ip_address

    print(f"Loaded {len(ip_roll_map)} registrations into memory.")
    yield
    signal.signal(signal.SIGHUP, previous_sighup_handler)
    print("Application shutting down...")

app = FastAPI(lifespan=lifespan)

app.mount("/clients", StaticFiles(directory="clients"), name="clients")


@app.middleware("http")
async def ip_restriction_middleware(request: Request, call_next):
    reload_config_if_changed()
    client_ip = request.client.host
    request_path = request.url.path
    current_time = datetime.now()

    is_allowed_public_path = False
    if (request_path == "/leaderboard" or
        request_path == "/api/leaderboard" or
        request_path.startswith("/api/history/") or
        request_path.startswith("/download/") or
        request_path.startswith("/clients/") or
        request_path == "/submission-status" or
            request_path == "/favicon.ico"):

        is_allowed_public_path = True

    if request_path in ["/docs", "/redoc", "/openapi.json"]:
        is_allowed_public_path = True

    # Extract roll number from ip_roll_map using client IP
    roll_no = None
    for r_no, ip in ip_roll_map.items():
        if ip == client_ip:
            roll_no = r_no
            break

    is_privileged = roll_no in pwd_rolls if roll_no else False

    # Reject everyone before start time
    # if current_time < lab_config["start_time"]:
    #     return JSONResponse(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         content={"detail": "Lab has not started yet. Access denied."}
    #     )

    # Reject if after end time and not privileged
    if not DEBUG and not is_allowed_public_path and current_time > lab_config["end_time"] and not is_privileged:
        path = request.url.path
        if not (path.startswith("/submit/") or path.startswith("/history/") or path.startswith("/task-status/") or path.startswith("/download/")):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Lab has ended. No more submissions allowed."}
            )

    allowed_subnets = lab_config.get("allowed_subnets", ["127.0."])
    is_safe_ip = False
    if client_ip:
        for subnet in allowed_subnets:
            if client_ip.startswith(subnet):
                is_safe_ip = True
                break

    if DEBUG:
        is_safe_ip = True

    if is_safe_ip:
        response = await call_next(request)
        return response

    if is_allowed_public_path:
        print(
            f"ALLOWED: Non-standard IP {client_ip} accessing public endpoint {request_path}")
        response = await call_next(request)
        return response

    print(
        f"BLOCKED: Non-standard IP {client_ip} tried to access restricted path {request_path}")

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": f"Access from your IP ({client_ip}) to this endpoint is not permitted."}
    )

# Registration and IP logging


@app.get("/starter/{roll_no}")
async def starter_kit(request: Request, roll_no: str):
    client_ip = request.client.host  # type: ignore
    capitalized_roll_no = roll_no.upper()

    if capitalized_roll_no not in student_list and roll_no not in student_list:
        return JSONResponse({
            "response": "YOU ARE NOT REGISTERED!!!"
        })

    async with file_lock:
        registered_ip = ip_roll_map.get(capitalized_roll_no)

        # Check for re-registration: same roll number from different IP
        if registered_ip and registered_ip != client_ip:
            write_header = not os.path.exists(VIOLATIONS_FILE)
            with open(VIOLATIONS_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        ["timestamp", "violation_type", "roll_no", "expected_ip", "actual_ip"])
                writer.writerow([datetime.now().isoformat(
                ), "Re-register Violation", capitalized_roll_no, registered_ip, client_ip])
            print(
                f"⚠️ LOGGED: Re-registration for {capitalized_roll_no}. IP changed from {registered_ip} to {client_ip}")

        # Check for IP collision: different roll number trying to use an already bound IP
        old_roll_for_ip = None
        for r_no, ip in ip_roll_map.items():
            if ip == client_ip and r_no != capitalized_roll_no:
                old_roll_for_ip = r_no
                break

        if old_roll_for_ip:
            write_header = not os.path.exists(VIOLATIONS_FILE)
            with open(VIOLATIONS_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        ["timestamp", "violation_type", "roll_no", "expected_ip", "actual_ip"])
                writer.writerow([datetime.now().isoformat(
                ), "IP Collision", capitalized_roll_no, "N/A", client_ip])
            print(
                f"⚠️ LOGGED: IP Collision - {capitalized_roll_no} logged from {client_ip} (previously bound to {old_roll_for_ip})")
            # Remove the old binding
            del ip_roll_map[old_roll_for_ip]

        ip_roll_map[capitalized_roll_no] = client_ip

        with open(REGISTRATIONS_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["roll_no", "ip_address"])  # Header
            for r_no, ip in ip_roll_map.items():
                writer.writerow([r_no, ip])

    path_to_file = f"./statics/{lab_config['lab_name']}.zip"
    if not os.path.exists(path_to_file):
        raise HTTPException(
            status_code=404, detail="Starter kit not found on server")

    return FileResponse(
        path=path_to_file,
        filename=f"{lab_config['lab_name']}.zip",
        media_type='application/zip'
    )

# Re-registration


@app.get("/rebind/{roll_no}")
async def rebind(request: Request, roll_no: str):
    client_ip = request.client.host  # type: ignore
    capitalized_roll_no = roll_no.upper()

    async with file_lock:
        registered_ip = ip_roll_map.get(capitalized_roll_no)

        if not registered_ip:
            return JSONResponse(
                status_code=403,
                content={
                    "response": "You are not registered, rebinding FORBIDDEN!!!"}
            )

        # Check for re-registration: same roll number from different IP
        if registered_ip and registered_ip != client_ip:
            write_header = not os.path.exists(VIOLATIONS_FILE)
            with open(VIOLATIONS_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        ["timestamp", "violation_type", "roll_no", "expected_ip", "actual_ip"])
                writer.writerow([datetime.now().isoformat(
                ), "Re-register Violation", capitalized_roll_no, registered_ip, client_ip])
            print(
                f"⚠️ LOGGED: Re-registration for {capitalized_roll_no}. IP changed from {registered_ip} to {client_ip}")

        # Check for IP collision: different roll number trying to use an already bound IP
        old_roll_for_ip = None
        for r_no, ip in ip_roll_map.items():
            if ip == client_ip and r_no != capitalized_roll_no:
                old_roll_for_ip = r_no
                break

        if old_roll_for_ip:
            write_header = not os.path.exists(VIOLATIONS_FILE)
            with open(VIOLATIONS_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        ["timestamp", "violation_type", "roll_no", "expected_ip", "actual_ip"])
                writer.writerow([datetime.now().isoformat(
                ), "IP Collision", capitalized_roll_no, "N/A", client_ip])
            print(
                f"⚠️ LOGGED: IP Collision - {capitalized_roll_no} logged from {client_ip} (previously bound to {old_roll_for_ip})")
            # Remove the old binding
            del ip_roll_map[old_roll_for_ip]

        ip_roll_map[capitalized_roll_no] = client_ip

        with open(REGISTRATIONS_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["roll_no", "ip_address"])  # Header
            for r_no, ip in ip_roll_map.items():
                writer.writerow([r_no, ip])

    return JSONResponse({
        "Status": "Re-registration Successfull!!!"
    })


# Leaderboard UI
@app.get("/leaderboard", response_class=HTMLResponse)
async def serve_leaderboard_ui(request: Request):
    try:
        return FileResponse("leaderboard.html")
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"detail": "leaderboard.html not found."})

# Leaderboard API


@app.get("/api/leaderboard")
async def get_leaderboard_data():
    base_dir = "submissions"
    if not os.path.isdir(base_dir):
        return JSONResponse(status_code=404, content={"detail": "No submissions found."})

    student_scores = {}

    for qno in os.listdir(base_dir):
        q_dir = os.path.join(base_dir, qno)
        if os.path.isdir(q_dir):
            for roll_dir in os.listdir(q_dir):
                student_path = os.path.join(q_dir, roll_dir)
                if os.path.isdir(student_path):
                    marks_log_path = os.path.join(student_path, "marks.txt")
                    if os.path.exists(marks_log_path):
                        max_marks = -1
                        try:
                            with open(marks_log_path, "r") as f:
                                for line in f:
                                    try:
                                        marks = float(
                                            line.strip().split(',')[1])
                                        if marks > max_marks:
                                            max_marks = marks
                                    except (IndexError, ValueError):
                                        continue
                            if max_marks != -1:
                                if roll_dir not in student_scores:
                                    student_scores[roll_dir] = {
                                        "scores": {}, "total_marks": 0.0}
                                student_scores[roll_dir]["scores"][qno] = max_marks
                                student_scores[roll_dir]["total_marks"] += max_marks
                        except Exception:
                            continue

    leaderboard_data = []
    for roll, data in student_scores.items():
        leaderboard_data.append({
            "roll": roll,
            "scores": data["scores"],
            "total_marks": data["total_marks"]
        })

    if not leaderboard_data:
        return JSONResponse(content=[])

    # Sort by total_marks (descending) to determine ranks
    sorted_data = sorted(
        leaderboard_data, key=lambda x: x["total_marks"], reverse=True)

    # Assign ranks
    ranked_leaderboard = []
    last_mark = -1
    current_rank = 0
    for i, entry in enumerate(sorted_data):
        if entry["total_marks"] != last_mark:
            current_rank = i + 1

        entry["rank"] = current_rank
        ranked_leaderboard.append(entry)
        last_mark = entry["total_marks"]

    return JSONResponse(content=ranked_leaderboard)

# History API


@app.get("/api/history/{qno}")
async def get_history(request: Request, qno: str):
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Authenticate via ip_roll_map
    roll_no = None
    for r_no, ip in ip_roll_map.items():
        if ip == client_ip:
            roll_no = r_no
            break

    if not roll_no:
        return JSONResponse(status_code=403, content={"detail": "You are not registered from this IP."})

    qno_upper = qno.upper()
    if qno_upper.isdigit():
        qno_upper = f"Q{qno_upper}"
    marks_log_path = os.path.join(
        "submissions", qno_upper, roll_no, "marks.txt")

    if not os.path.exists(marks_log_path):
        return JSONResponse(content=[])

    history_data = []
    serial = 1
    with open(marks_log_path, "r") as f:
        for line in f:
            try:
                parts = line.strip().split(',')
                timestamp = parts[0].strip()
                marks = float(parts[1].strip())
                history_data.append({
                    "sn": serial,
                    "timestamp": timestamp,
                    "marks": marks
                })
                serial += 1
            except (IndexError, ValueError):
                continue

    return JSONResponse(content=history_data)

# Download API


@app.get("/download/{qno}/{sn}")
async def download_submission(request: Request, qno: str, sn: int):
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Authenticate via ip_roll_map
    roll_no = None
    for r_no, ip in ip_roll_map.items():
        if ip == client_ip:
            roll_no = r_no
            break

    if not roll_no:
        return JSONResponse(status_code=403, content={"detail": "You are not registered from this IP."})

    qno_upper = qno.upper()
    if qno_upper.isdigit():
        qno_upper = f"Q{qno_upper}"
    marks_log_path = os.path.join(
        "submissions", qno_upper, roll_no, "marks.txt")

    if not os.path.exists(marks_log_path):
        raise HTTPException(status_code=404, detail="No submissions found.")

    target_timestamp = None
    current_sn = 1
    with open(marks_log_path, "r") as f:
        for line in f:
            try:
                parts = line.strip().split(',')
                if current_sn == sn:
                    target_timestamp = parts[0].strip()
                    break
                current_sn += 1
            except IndexError:
                continue

    if not target_timestamp:
        raise HTTPException(status_code=404, detail="Invalid Serial Number.")

    # Search for the source code file matching the timestamp
    student_dir = os.path.join("submissions", qno_upper, roll_no)
    search_pattern = os.path.join(student_dir, f"*_{target_timestamp}.*")

    matching_files = glob.glob(search_pattern)
    source_file = None

    for file in matching_files:
        # Exclude the result logs and submission executables
        if not file.endswith(".txt") and not file.endswith(".out"):
            source_file = file
            break

    if not source_file:
        raise HTTPException(
            status_code=404, detail="Source code file not found for this submission.")

    return FileResponse(
        path=source_file,
        filename=os.path.basename(source_file),
        media_type='application/octet-stream'
    )

# Async Grading Submission Endpoint


@app.post("/submit/{qno}")
async def handleSubmit(
    qno: str,
    request: Request,
    roll: str = Form(...),
    file: UploadFile = File(...)
):

    client_ip = request.client.host  # type: ignore
    qno_upper = qno.upper()
    if "questions" in lab_config and qno_upper not in lab_config["questions"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid question '{qno_upper}'. Allowed questions are: {', '.join(lab_config['questions'])}")

    roll_upper = roll.upper()

    registered_ip = ip_roll_map.get(roll_upper)
    if not registered_ip:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Roll number '{roll_upper}' is not registered. Please call /starter/{{your_roll_no}} first.")

    if client_ip != registered_ip:
        async with file_lock:
            write_header = not os.path.exists(VIOLATIONS_FILE)
            with open(VIOLATIONS_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(
                        ["timestamp", "violation_type", "roll_no", "expected_ip", "actual_ip"])
                writer.writerow([datetime.now().isoformat(
                ), "Submit Violation", roll_upper, registered_ip, client_ip])

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Violation: Submission from an unregistered IP. Incident logged.")

    file_content = await file.read()

    current_time = datetime.now()
    submission_timestamp = current_time.strftime("%Y%m%d-%H%M%S")
    is_late = False
    is_privileged = roll_upper in pwd_rolls
    if not DEBUG and current_time > lab_config["end_time"] and not is_privileged:
        # Check if already submitted late for this question
        late_dir = os.path.join("late_submissions", qno_upper, roll_upper)
        if os.path.exists(late_dir) and len(os.listdir(late_dir)) > 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"You have already exhausted your single late submission for {qno_upper}.")

        is_late = True

    work = handle_submission.delay(
        qno_upper, roll_upper, file.filename, file_content, is_late, submission_timestamp)

    return JSONResponse(
        {
            "taskid": work.id
        }
    )


@app.get("/submission-status")
async def get_submission_status():
    base_submission_dir = "submissions"

    question_dirs = ['Q1']

    if not question_dirs:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "No question submission directories found in 'submissions'."}
        )

    registered_students = ip_roll_map.keys()

    report = {}

    for roll_no in registered_students:
        student_status = {}
        for qno in question_dirs:
            submission_path = os.path.join(base_submission_dir, qno, roll_no)
            student_status[qno] = os.path.isdir(submission_path)

        report[roll_no] = student_status

    return JSONResponse(content=report)


@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):

    async_result = AsyncResult(task_id)
    return JSONResponse(
        {
            "task-id": task_id,
            "result": async_result.result,
            "status": async_result.status
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
