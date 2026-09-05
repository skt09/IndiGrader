#!/usr/bin/env python3
"""Verify submitted source files against the lab's configured testcases.

This script mirrors the workflow of the project builder and grader:
1. Find config.json beside the .admin folder.
2. If it is missing, ask the user for its path.
3. Read the question list and per-question `ext` fields.
4. Prompt for one source file per question.
5. Run `grade.sh` against every available testcase directory.
6. Report any wrong answers, timeouts, runtime errors, or compile failures.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import glob
import platform
from pathlib import Path
from typing import Dict, List, Optional

try:
    import readline
except ImportError:
    readline = None

_IS_LIBEDIT = readline is not None and "libedit" in (
    getattr(readline, "__doc__", "") or "")

CYAN = '\033[1;36m'
GREEN = '\033[1;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
RESET = '\033[0m'

ALLOWED_EXTENSIONS = {
    ".c", ".cpp", ".py", ".awk", ".gz",
}


def _rl_prompt(text):
    """Wrap ANSI codes in readline's invisible-character markers so it can
    compute the real prompt width (otherwise long lines wrap incorrectly).
    libedit (macOS) doesn't use the \001/\002 convention and mangles the
    escape codes if we send them, so it gets the plain colored prompt."""
    if readline is None or _IS_LIBEDIT:
        return CYAN + text + RESET
    return "\001" + CYAN + "\002" + text + "\001" + RESET + "\002"


def expand_path(path):
    """Expand ~, $VARS and surrounding quotes/escapes into a usable path."""
    path = path.strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in ("'", '"'):
        path = path[1:-1]
    else:
        path = path.replace("\\ ", " ")
    return os.path.expanduser(os.path.expandvars(path))


def _path_completer(text, state):
    """Tab-completion over the filesystem, tilde-aware."""
    try:
        expanded = expand_path(text)
        matches = sorted(glob.glob(expanded + "*"))
        results = []
        for m in matches:
            display = m
            if text.startswith("~"):
                home = os.path.expanduser("~")
                if m.startswith(home):
                    display = "~" + m[len(home):]
            results.append(display + os.sep if os.path.isdir(m) else display)
        return results[state] if state < len(results) else None
    except Exception:
        return None


def _readline_enabled():
    return readline is not None and sys.stdin.isatty()


def _with_path_completion(enable):
    """Turn filesystem tab-completion on/off around a path prompt."""
    if readline is None or not _readline_enabled():
        return
    if enable:
        readline.set_completer_delims("")
        readline.set_completer(_path_completer)
        if _IS_LIBEDIT:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
    else:
        readline.set_completer(None)


def _detect_file_picker():
    """Returns the available native file picker backend, or None."""
    def _cmd_exists(cmd):
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    if platform.system() == "Darwin":
        return "osascript"
    if _cmd_exists("zenity"):
        return "zenity"
    if _cmd_exists("kdialog"):
        return "kdialog"
    try:
        import tkinter  # noqa: F401
        return "tkinter"
    except ImportError:
        pass
    return None


FILE_PICKER = _detect_file_picker()
LAST_BROWSED_DIR = os.getcwd()


def _native_browse(prompt_text, is_dir=False):
    """Opens the OS-native file picker. Returns the selected path or empty string."""
    global LAST_BROWSED_DIR
    path = ""
    if FILE_PICKER == "zenity":
        cmd = ["zenity", "--file-selection", "--title",
               prompt_text, f"--filename={LAST_BROWSED_DIR}/"]
        if is_dir:
            cmd.append("--directory")
        result = subprocess.run(cmd, capture_output=True, text=True)
        path = result.stdout.strip()

    elif FILE_PICKER == "kdialog":
        if is_dir:
            cmd = ["kdialog", "--getexistingdirectory",
                   LAST_BROWSED_DIR, "--title", prompt_text]
        else:
            cmd = ["kdialog", "--getopenfilename",
                   LAST_BROWSED_DIR, "--title", prompt_text]
        result = subprocess.run(cmd, capture_output=True, text=True)
        path = result.stdout.strip()

    elif FILE_PICKER == "osascript":
        if is_dir:
            script = f'tell app "Finder" to POSIX path of (choose folder with prompt "{prompt_text}" default location POSIX file "{LAST_BROWSED_DIR}")'
        else:
            script = f'tell app "Finder" to POSIX path of (choose file with prompt "{prompt_text}" default location POSIX file "{LAST_BROWSED_DIR}")'
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True)
        path = result.stdout.strip()

    elif FILE_PICKER == "tkinter":
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            root.tk.call("set", "::tk::dialog::file::showHiddenVar", "0")
        except Exception:
            pass
        path = filedialog.askdirectory(initialdir=LAST_BROWSED_DIR, title=prompt_text) if is_dir else filedialog.askopenfilename(
            initialdir=LAST_BROWSED_DIR, title=prompt_text)
        root.destroy()
        path = path or ""

    if path and os.path.exists(path):
        LAST_BROWSED_DIR = os.path.dirname(
            path) if os.path.isfile(path) else path

    return path


def get_path_input(prompt_text, is_dir=False, allow_blank=False, default_val=""):
    while True:
        browse_hint = " (type 'b' to browse)" if FILE_PICKER else ""
        blank_hint = " (leave blank to skip)" if allow_blank and not default_val else ""
        default_hint = f" [{default_val}]" if default_val else ""
        tab_hint = " (TAB to complete)" if _readline_enabled() else ""
        _with_path_completion(True)
        try:
            user_input = input(_rl_prompt(
                f"{prompt_text}{default_hint}{blank_hint}{browse_hint}{tab_hint}: "
            )).strip()
        finally:
            _with_path_completion(False)

        path_to_check = None
        if not user_input and default_val:
            path_to_check = default_val
        elif allow_blank and user_input == "":
            return ""
        elif FILE_PICKER and user_input.lower() in ['b', 'browse']:
            path = _native_browse(prompt_text, is_dir=is_dir)
            if path:
                print(GREEN + f"[*] Selected: {path}" + RESET)
                return path
            print(
                YELLOW + "[-] Browse cancelled. Please type the path or try again." + RESET)
            continue
        elif user_input:
            path_to_check = user_input

        if path_to_check is not None:
            resolved = expand_path(path_to_check)
            if os.path.exists(resolved):
                return resolved
            print(
                RED + f"[-] ERROR: Path '{path_to_check}' does not exist. Please try again." + RESET)


def find_config_file() -> Optional[Path]:
    """Auto-discover config.json one directory above .admin."""
    admin_dir = Path(__file__).resolve().parent
    candidate = admin_dir.parent / "config.json"
    if candidate.is_file():
        return candidate
    return None


def prompt_for_path(prompt: str, required_ext: Optional[str] = None) -> Path:
    """Ask the user for an existing file path using the same file-input UX as builder.py."""
    while True:
        raw_path = get_path_input(prompt, is_dir=False, allow_blank=False)
        path = Path(raw_path).expanduser().resolve()

        if not path.exists():
            print(f"[-] File not found: {path}")
            continue
        if not path.is_file():
            print(f"[-] This is not a file: {path}")
            continue

        if required_ext:
            ext = path.suffix.lower()
            if ext != required_ext.lower():
                print(
                    f"[-] Wrong extension: expected {required_ext.lower()}, got {ext or 'none'}")
                continue
        else:
            ext = path.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                print(
                    "[-] Unsupported file type. Please provide one of: "
                    + ", ".join(sorted(ALLOWED_EXTENSIONS))
                )
                continue

        return path


def load_config(config_path: Path) -> Dict:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Config file is not a valid JSON object: {config_path}")

    return data


def get_questions(config_data: Dict) -> List[str]:
    questions = config_data.get("questions")
    if isinstance(questions, list) and questions:
        return [str(q) for q in questions]

    pattern = re.compile(r"^Q\d+$", re.IGNORECASE)
    return sorted([key for key in config_data.keys() if pattern.match(str(key))])


def normalize_ext(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    return value if value.startswith(".") else f".{value}"


def resolve_testcase_dirs(config_path: Path, lab_name: str) -> List[Path]:
    root_dir = config_path.parent
    dirs: List[Path] = []

    private_dir = root_dir / "testcases"
    if private_dir.is_dir():
        dirs.append(private_dir)

    static_dir = root_dir / "statics" / lab_name / "testcases"
    if static_dir.is_dir():
        dirs.append(static_dir)

    # Deduplicate while preserving order.
    unique_dirs: List[Path] = []
    seen = set()
    for d in dirs:
        real = d.resolve()
        if real not in seen:
            seen.add(real)
            unique_dirs.append(real)

    if not unique_dirs:
        print(
            f"[-] No testcase directories found at: {private_dir} or {static_dir}")

    return unique_dirs


def ask_for_submission_file(question: str, config_data: Dict) -> Path:
    qcfg = config_data.get(question, {})
    ext = normalize_ext(qcfg.get("ext", ""))

    if ext:
        print(f"[*] {question} requires extension: {ext}")
        return prompt_for_path(f"Select source file for {question}", required_ext=ext)

    print(
        f"[*] {question} has no fixed extension; any supported source file is accepted.")
    return prompt_for_path(f"Select source file for {question}")


def run_grade_script(config_path: Path, question: str, submission: Path, testcase_dir: Path) -> subprocess.CompletedProcess:
    grader = config_path.parent / "grade.sh"
    if not grader.exists():
        raise FileNotFoundError(f"grade.sh not found at {grader}")

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
        str(config_path),
        "--sandbox"
    ]

    return subprocess.run(cmd, cwd=str(config_path.parent), capture_output=True, text=True)


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


def main() -> int:
    print("IndiGrader Testcase Verifier")
    print("=" * 50)

    config_path = find_config_file()
    if config_path is None:
        print("[-] config.json not found next to .admin.")
        config_path = prompt_for_path(
            "Path to config.json", required_ext=".json")

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

    print(f"[*] Found lab: {lab_name}")
    print(f"[*] Questions: {', '.join(question_names)}")

    submissions: Dict[str, Path] = {}
    for question in question_names:
        submissions[question] = ask_for_submission_file(question, config_data)

    testcase_dirs = resolve_testcase_dirs(config_path, lab_name)
    if not testcase_dirs:
        return 1

    overall_failed = False
    for question in question_names:
        submission = submissions[question]
        failed_in_any_dir = False

        for testcase_dir in testcase_dirs:
            try:
                result = run_grade_script(
                    config_path, question, submission, testcase_dir)
            except Exception as exc:
                print(f"\n===== {question} :: {testcase_dir} =====")
                print(f"[-] Error while running grader: {exc}")
                failed_in_any_dir = True
                overall_failed = True
                continue

            failed = print_run_result(question, testcase_dir, result)
            if failed:
                failed_in_any_dir = True
                overall_failed = True

        if not failed_in_any_dir:
            print(f"[*] {question}: passed all available testcase directories.")

    if overall_failed:
        print("\n[RESULT] One or more testcase checks failed. Review the output above for the failing diff and verdicts.")
        return 1

    print("\n[RESULT] All submitted files passed every available testcase directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
