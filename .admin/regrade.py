import os
import csv
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


def find_config_file() -> Optional[Path]:
    """Auto-discover config.json one directory above .admin."""
    admin_dir = Path(__file__).resolve().parent
    candidate = admin_dir.parent / "config.json"
    if candidate.is_file():
        return candidate
    return None


def load_config(config_path: Path) -> Dict:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Config file is not a valid JSON object: {config_path}")

    return data


def get_questions(config_data: Dict) -> List[str]:
    """Extracts question names from the config."""
    questions = config_data.get("questions")
    if isinstance(questions, list) and questions:
        return [str(q) for q in questions]

    pattern = re.compile(r"^Q\d+$", re.IGNORECASE)
    return sorted([key for key in config_data.keys() if pattern.match(str(key))])


def resolve_testcase_dirs(config_path: Path, lab_name: str) -> List[Path]:
    root_dir = config_path.parent
    dirs: List[Path] = []

    private_dir = root_dir / "testcases"
    if private_dir.is_dir():
        dirs.append(private_dir)

    # static_dir = root_dir / "statics" / lab_name / "testcases"
    # if static_dir.is_dir():
    #     dirs.append(static_dir)

    # Deduplicate while preserving order.
    unique_dirs: List[Path] = []
    seen = set()
    for d in dirs:
        real = d.resolve()
        if real not in seen:
            seen.add(real)
            unique_dirs.append(real)

    if not unique_dirs:
        print(f"[-] No testcase directories found at: {private_dir}") #or {static_dir}") 

    return unique_dirs


def get_highest_mark(marks_file):
    highest_mark = -1.0
    best_timestamp = None
    try:
        with open(marks_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    ts_str, mark_str = parts
                    try:
                        mark = float(mark_str)
                        if mark > highest_mark:
                            highest_mark = mark
                            best_timestamp = ts_str
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error reading {marks_file}: {e}")
    return highest_mark, best_timestamp


def load_and_initialize_report(submissions_dir):
    """
    Traverses the submissions directory, reads original marks from marks.txt,
    and initializes a dictionary to track before vs after changes.
    """
    report_data = {}
    
    if not os.path.exists(submissions_dir):
        print(f"[-] ERROR: '{submissions_dir}' folder not found when trying to load original marks.")
        return report_data

    # Loop through student roll number folders (matching the structure expected in main)
    for roll_dir in os.listdir(submissions_dir):
        student_path = os.path.join(submissions_dir, roll_dir)
        if not os.path.isdir(student_path):
            continue
            
        # Loop through question folders (e.g., Q1, Q2) inside the student's directory
        for q_dir in os.listdir(student_path):
            q_path = os.path.join(student_path, q_dir)
            if not os.path.isdir(q_path):
                print(str(q_path)+" path does not exist")
                continue
                
            marks_file = os.path.join(q_path, "marks.txt")
            if os.path.exists(marks_file):
                mark, _ = get_highest_mark(marks_file)
                if mark >= 0:
                    if roll_dir not in report_data:
                        report_data[roll_dir] = {}
                    
                    # Directly initialize the reporting structure with the original mark
                    report_data[roll_dir][q_dir] = {
                        'Original_Mark': mark,
                        'New_Mark': None, 
                        'Delta': None     
                    }
    return report_data


def normalize_ext(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    return value if value.startswith(".") else f".{value}"


def find_submission_path(student_dir: Path, question: str, config_data: Dict) -> Optional[Path]:
    """Searches a student's directory for the correct submission format."""
    qcfg = config_data.get(question, {})

    # 1. Handle Makefile Mode
    if qcfg.get("makefile", False):
        project_dir = student_dir / question
        if project_dir.is_dir():
            makefile_names = ("Makefile", "makefile", "GNUmakefile")
            if any((project_dir / name).is_file() for name in makefile_names):
                return project_dir
        return None

    # 2. Handle specific extension
    ext = normalize_ext(qcfg.get("ext", ""))
    if ext:
        expected_file = student_dir / f"{question}{ext}"
        if expected_file.is_file():
            return expected_file
        return None

    # 3. Handle no fixed extension (find any file named question.*)
    for file_path in student_dir.glob(f"{question}.*"):
        if file_path.is_file():
            return file_path
            
    return None


def get_makefile_target(project_dir: Path) -> Optional[str]:
    """Read the first explicit target from a Makefile project."""
    makefile_names = ("Makefile", "makefile", "GNUmakefile")
    makefile_path = next(
        (project_dir / name for name in makefile_names if (project_dir / name).is_file()),
        None,
    )
    if makefile_path is None:
        return None

    target_pattern = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(?![=])")
    assignment_pattern = re.compile(
        r"^\s*(?:TARGET\s*[:?+]?=|.*\s-o)\s*([A-Za-z0-9_.-]+)\b"
    )
    try:
        for line in makefile_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = target_pattern.match(line)
            if match and match.group(1) not in {"all", "clean"}:
                return match.group(1)
            match = assignment_pattern.match(line)
            if match:
                return match.group(1)
    except OSError:
        return None
    return None



def run_grade_script(config_path: Path, question: str, submission: Path, testcase_dir: Path) -> subprocess.CompletedProcess:
    grader = config_path.parent / "grade.sh"
    if not grader.exists():
        raise FileNotFoundError(f"grade.sh not found at {grader}")

    run_config = config_path
    temporary_config = None
    question_config = load_config(config_path).get(question, {})
    
    if question_config.get("makefile", False):
        makefile_target = get_makefile_target(submission)
        if makefile_target:
            config_data = load_config(config_path)
            config_data[question] = dict(config_data.get(question, {}))
            config_data[question]["executable_name"] = makefile_target
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=config_path.parent,
                prefix=".ig_verify_config_",
                suffix=".json",
                delete=False,
            ) as config_file:
                json.dump(config_data, config_file, indent=2)
                temporary_config = Path(config_file.name)
            run_config = temporary_config

    cmd = [
        "bash",
        str(grader),
        "--submission",
        str(submission),
        "--question",
        question,
        "--testcases_dir",
        str(testcase_dir),
        "--config",
        str(run_config),
    ]

    try:
        return subprocess.run(cmd, cwd=str(config_path.parent), capture_output=True, text=True)
    finally:
        if temporary_config is not None:
            temporary_config.unlink(missing_ok=True)


def print_run_result(question: str, testcase_dir: Path, result: subprocess.CompletedProcess) -> bool:
    print(f"\n===== {question} :: {testcase_dir} =====")
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        print(output.strip())
    else:
        print("[LOG] No output captured.")

    failure_tokens = (
        "WRONG_ANSWER",
        "TIMEOUT",
        "RUNTIME_ERROR",
        "COMPILATION_ERROR",
        "No input directory found",
        "Config file not found",
        "Missing required arguments",
    )

    return any(token in output for token in failure_tokens)

def extract_test_counts(stdout_str: str) -> tuple[int, int]:
    """
    Parses the stdout of the grader script.
    Returns a tuple of (passed_cases, total_cases).
    """
    passed = 0
    total = 0
    
    for line in stdout_str.splitlines():
        line = line.strip()
        
        if line.startswith("[VERDICT]"):
            parts = line.replace("[VERDICT]", "").strip().split(":", 1)
            
            if len(parts) == 2:
                test_name = parts[0].strip()
                verdict = parts[1].strip()
                
                # If compilation fails, return 0 passed and 0 total 
                # (or change the second 0 to your expected test count if needed)
                if test_name == "ALL" and verdict == "COMPILATION_ERROR":
                    return 0, 0
                
                if test_name != "ALL":
                    total += 1
                    if verdict.startswith("PASSED"):
                        passed += 1

    return passed, total

def main() -> int:
    print("IndiGrader Batch Re-evaluator")
    print("=" * 50)

    config_path = find_config_file()
    if config_path is None:
        print("[-] config.json not found next to .admin.")
        return 1

    try:
        config_data = load_config(config_path)
    except Exception as exc:
        print(f"[-] Could not read config file: {exc}")
        return 1

    lab_name = str(config_data.get("lab_name", "")).strip()
    if not lab_name:
        print("[-] config.json does not contain a valid lab_name field.")
        return 1

    question_names = get_questions(config_data)
    if not question_names:
        print("[-] No questions were found in config.json.")
        return 1

    testcase_dirs = resolve_testcase_dirs(config_path, lab_name)
    if not testcase_dirs:
        return 1

    print(f"[*] Found lab: {lab_name}")
    print(f"[*] Questions: {', '.join(question_names)}")

    orginal_marks_dir = config_path.parent / "submissions"
    
    # Load marks and initialize the report dictionary
    report_data = load_and_initialize_report(orginal_marks_dir)
    
    if report_data:
        print(f"[*] Initialized comparison report data for {len(report_data)} students.")

    submissions_dir=config_path.parent /"highest_submissions_by_stu"
    for student_dir in submissions_dir.iterdir():
        if not student_dir.is_dir():
            continue
        
        student_id = student_dir.name
        for question in question_names:
            submission_path = find_submission_path(student_dir, question, config_data)
            entry = report_data.setdefault(question, {}).setdefault(student_id, {'Original_Mark': 0.0})
            if not submission_path:
                print(f"[-] Missing submission for {student_id} - {question}")
                entry['New_Mark'] = 0.0
                entry['Delta'] = 0.0 - entry['Original_Mark']
                continue
                
            print(f"[*] Evaluating {student_id} for {question} at {submission_path}")

            qcfg = config_data.get(question, {})
            full_marks = float(qcfg.get("full_marks", 100.0))
            total_passed=0;
            total_cases=0;
            
            for testcase_dir in testcase_dirs:
                try:
                    result = run_grade_script(
                        config_path, question, submission_path, testcase_dir
                    )
                    
                    has_failed = print_run_result(question, testcase_dir, result)

                    if has_failed:
                        print(f"[-] Fatal error or Compilation failure for {student_id} on {question}. Awarding 0.")
                    else:
                        passed,total = extract_test_counts(result.stdout)
                        total_cases+=total
                        total_passed+=passed 
                    
                except Exception as exc:
                    print(f"[-] Error for {student_id} on {question}: {exc}")
                    continue
            if total_cases > 0:
                total_new_mark = round((total_passed / total_cases) * full_marks, 2)
            else:
                total_new_mark = 0.0
            original_mark = float(entry.get('Original_Mark', 0.0))
            entry['New_Mark'] = total_new_mark
            entry['Delta'] = total_new_mark - original_mark
            
            print(f"    -> Original: {original_mark} | New: {total_new_mark} | Delta: {entry['Delta']}")



    csv_path = config_path.parent / "before_vs_after.csv"
    print(f"\n[*] Batch evaluation complete. Writing report to {csv_path}...")
    with open(csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Student_ID", "Question", "Original_Mark", "New_Mark", "Delta"])

        # Sort questions alphabetically (e.g., Q1, Q2)
        for question in sorted(report_data.keys()):
            students = report_data[question]
            
            # Sort student IDs alphabetically (e.g., CS28B001, CS28B002)
            for student_id in sorted(students.keys()):
                data = students[student_id]
                
                # Safely round Delta only if it is not None
                delta = data.get('Delta')
                writer.writerow([
                    student_id,
                    question,
                    data.get('Original_Mark'),
                    data.get('New_Mark'),
                    delta
                ])
    print("\n[RESULT] Batch re-evaluation complete. Check before_vs_after.csv for results.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())