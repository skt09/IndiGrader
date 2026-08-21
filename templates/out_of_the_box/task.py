import os
import time
import glob
import subprocess
import re

from celery import Celery

# List of allowed file extensions
ALLOWED_EXTENSIONS = [".c", ".cpp", ".py", ".awk", ".gz"]

capp = Celery(
    'task',
    broker="redis://localhost:6379",
    backend="redis://localhost:6379"
)

@capp.task(name="handle-sub")
def handle_submission(qno: str, roll: str, save_file: str, is_late: bool = False, submission_timestamp: str = None):
    qno_upper = qno.upper()
    roll_upper = roll.upper()
    
    import json
    with open("config.json", "r") as f:
        config_data = json.load(f)
    
    fm = config_data.get(qno_upper, {}).get("full_marks", 100)
    timeouter = config_data.get(qno_upper, {}).get("timeout", 5)

    logs = [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Processing submission for Roll: {roll_upper}, Q-No: {qno_upper}\n"]

    base_dir = "late_submissions" if is_late else "submissions"
    q_dir = os.path.join(base_dir, qno_upper)
    std_dir = os.path.join(q_dir, roll_upper)

    timestamp = submission_timestamp if submission_timestamp else time.strftime("%Y%m%d-%H%M%S")
    base, ext = os.path.splitext(save_file)
    ext = ext.lower()

    log_path = os.path.join(std_dir, f"result_{timestamp}.txt")
    marks_log = os.path.join(std_dir, "marks.txt")

    if not os.path.exists(save_file):
        logs.append(f"ERROR: Source file not found at {save_file}\n")
        os.makedirs(std_dir, exist_ok=True)
        with open(log_path, "w") as log_file: log_file.writelines(logs)
        return {"status": "Setup Error", "message": "Source file missing."}

    logs.append(f"SUCCESS: Source file located at {save_file}\n")
    
    # Handle Archives for Makefile projects
    submission_path = save_file
    if ext == ".gz":
        extract_dir = os.path.join(std_dir, f"extracted_{timestamp}")
        os.makedirs(extract_dir, exist_ok=True)
        try:
            import tarfile
            with tarfile.open(save_file, "r:gz") as tar:
                tar.extractall(path=extract_dir)
            submission_path = os.path.join(extract_dir, qno_upper)
            logs.append(f"SUCCESS: Archive extracted to {submission_path}\n")
        except Exception as e:
            logs.append(f"ERROR: Failed to extract archive. Reason: {e}\n")
            with open(log_path, "w") as log_file: log_file.writelines(logs)
            return {"status": "Setup Error", "message": "Could not extract archive."}

    # Evaluate via grade.sh
    grade_cmd = [
        "./grade.sh",
        "--submission", submission_path,
        "--question", qno_upper,
        "--testcases_dir", "testcases",
        "--sandbox",
        "--config", "config.json"
    ]
    
    logs.append(f"INFO: Running grading script...\n")
    
    run_proc = subprocess.run(grade_cmd, capture_output=True, text=True, errors="replace")
    grade_output = run_proc.stdout
    
    results = {}
    passed = 0
    total = 0
    
    for line in grade_output.splitlines():
        logs.append(f"{line}\n")
        if line.startswith("[VERDICT]"):
            # e.g., [VERDICT] 01: PASSED
            parts = line.replace("[VERDICT]", "").strip().split(":", 1)
            if len(parts) == 2:
                test_name = parts[0].strip()
                verdict = parts[1].strip()
                # Ignore global COMPILATION_ERROR as a single test
                if test_name != "ALL":
                    results[test_name] = verdict
                    total += 1
                    if verdict.startswith("PASSED"):
                        passed += 1
                else:
                    results["Compilation"] = verdict
        elif line.startswith("[SCORE]"):
            pass # We calculate based on the parsed verdicts

    # Include stderr in logs if the script crashed or had errors
    if run_proc.stderr:
        logs.append(f"\n--- SCRIPT STDERR ---\n{run_proc.stderr}\n")

    # Wrap up logs and marks
    logs.append("\n--- FINAL RESULTS ---\n")
    for test, result in results.items():
        logs.append(f"{test}: {result}\n")

    if results.get("Compilation") == "COMPILATION_ERROR":
        with open(log_path, "w") as log_file: log_file.writelines(logs)
        with open(marks_log, "a") as f: f.write(f"{timestamp}, 0\n")
        return {"status": "Compilation Error", "details": "".join(logs)}

    with open(log_path, "w") as log_file: log_file.writelines(logs)

    failed = total - passed
    marks = round((passed / total) * fm, 2) if total > 0 else 0

    with open(marks_log, "a") as f: f.write(f"{timestamp}, {marks}\n")

    return {"status": "Finished", "results": results, "passed": passed, "failed": failed, "marks": marks, "full": fm}