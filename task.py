import os
import time
import glob
import subprocess
import re

from celery import Celery

# Runner configuration map
RUNNER_CONFIG = {
    ".c": {
        "compiled": True,
        "build_cmd": ["gcc", "{src}", "-lm", "-o", "{out}"],
        "run_cmd": ["{out}"]
    },
    ".cpp": {
        "compiled": True,
        "build_cmd": ["g++", "{src}", "-o", "{out}"],
        "run_cmd": ["{out}"]
    },
    ".py": {
        "compiled": False,
        "build_cmd": None,
        "run_cmd": ["python3", "{src}"]
    },
    ".awk": {
        "compiled": False,
        "build_cmd": None,
        "run_cmd": ["awk", "-f", "{src}"]
    }
}

capp = Celery(
    'task',
    broker="redis://localhost:6379",
    backend="redis://localhost:6379"
)

@capp.task(name="handle-sub")
def handle_submission(qno: str, roll: str, filename: str, content: bytes, is_late: bool = False):
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
    os.makedirs(std_dir, exist_ok=True) 

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    # Validate extension
    if ext not in RUNNER_CONFIG:
        logs.append(f"ERROR: Unsupported file extension: {ext}\n")
        log_path = os.path.join(std_dir, f"result_{timestamp}.txt")
        with open(log_path, "w") as log_file: log_file.writelines(logs)
        return {"status": "Setup Error", "message": f"Unsupported file type: {ext}"}

    config = RUNNER_CONFIG[ext]
    save_filename = f"{base}_{timestamp}{ext}"
    save_file = os.path.join(std_dir, save_filename)
    executable_path = os.path.join(std_dir, f"submission_{timestamp}.out")
    log_path = os.path.join(std_dir, f"result_{timestamp}.txt")
    marks_log = os.path.join(std_dir, "marks.txt")

    # Save source file
    try:
        with open(save_file, "wb") as f: f.write(content)
        logs.append(f"SUCCESS: Source file saved to {save_file}\n")
    except Exception as e:
        logs.append(f"ERROR: Failed to save source file. Reason: {e}\n")
        with open(log_path, "w") as log_file: log_file.writelines(logs)
        return {"status": "Setup Error", "message": "Could not save file."}
    
    # Evaluate via grade.sh
    grade_cmd = [
        "./grade.sh",
        "--submission", save_file,
        "--question", qno_upper,
        "--testcases_dir", "testcases",
        "--sandbox",
        "--config", "config.json"
    ]
    
    logs.append(f"INFO: Running grading script...\n")
    
    run_proc = subprocess.run(grade_cmd, capture_output=True, text=True)
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

    with open(log_path, "w") as log_file: log_file.writelines(logs)

    failed = total - passed
    marks = round((passed / total) * fm, 2) if total > 0 else 0

    with open(marks_log, "a") as f: f.write(f"{timestamp}, {marks}\n")

    return {"status": "Finished", "results": results, "passed": passed, "failed": failed, "marks": marks, "full": fm}