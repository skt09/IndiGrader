import os
import time

from celery import Celery

capp = Celery(
    'task',
    broker="redis://localhost:6379",
    backend="redis://localhost:6379"
)

@capp.task(name="handle-sub")
def handle_submission(qno: str, roll: str, filename: str, content: bytes, is_late: bool = False, submission_timestamp: str = None):
    qno_upper = qno.upper()
    roll_upper = roll.upper()
    
    logs = [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Processing submission for Roll: {roll_upper}, Q-No: {qno_upper}\n"]

    base_dir = "late_submissions" if is_late else "submissions"
    q_dir = os.path.join(base_dir, qno_upper)
    std_dir = os.path.join(q_dir, roll_upper)
    os.makedirs(std_dir, exist_ok=True) 

    timestamp = submission_timestamp if submission_timestamp else time.strftime("%Y%m%d-%H%M%S")
    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    save_filename = f"{base}_{timestamp}{ext}"
    save_file = os.path.join(std_dir, save_filename)
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
    
    # Grading has been bypassed for this submission-only lab
    logs.append(f"INFO: Grading bypassed. Marking as submitted.\n")
    logs.append("\n--- FINAL RESULTS ---\n")
    logs.append("Submission: PASSED\n")

    with open(log_path, "w") as log_file: log_file.writelines(logs)

    # Log 0 marks as requested for submission-only
    with open(marks_log, "a") as f: f.write(f"{timestamp}, 0\n")

    return {"status": "Finished", "results": {"Submission": "PASSED"}, "passed": 1, "failed": 0, "marks": 0, "full": 0}