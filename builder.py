#!/usr/bin/env python3
import os
import sys
import shutil
import json
from datetime import datetime, timedelta
import subprocess
import platform
import glob

CYAN = '\033[1;36m'
GREEN = '\033[1;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
RESET = '\033[0m'

try:
    import readline
except ImportError:  # Windows without pyreadline3
    readline = None

_IS_LIBEDIT = readline is not None and "libedit" in (getattr(readline, "__doc__", "") or "")

def _rl_prompt(text):
    if readline is None or _IS_LIBEDIT:
        return CYAN + text + RESET
    return "\001" + CYAN + "\002" + text + "\001" + RESET + "\002"

def expand_path(path):
    path = path.strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in ("'", '"'):
        path = path[1:-1]
    else:
        path = path.replace("\\ ", " ")
    return os.path.expanduser(os.path.expandvars(path))

def _path_completer(text, state):
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
    global LAST_BROWSED_DIR
    path = ""
    if FILE_PICKER == "zenity":
        cmd = ["zenity", "--file-selection", "--title", prompt_text, f"--filename={LAST_BROWSED_DIR}/"]
        if is_dir:
            cmd.append("--directory")
        result = subprocess.run(cmd, capture_output=True, text=True)
        path = result.stdout.strip()
    elif FILE_PICKER == "kdialog":
        if is_dir:
            cmd = ["kdialog", "--getexistingdirectory", LAST_BROWSED_DIR, "--title", prompt_text]
        else:
            cmd = ["kdialog", "--getopenfilename", LAST_BROWSED_DIR, "--title", prompt_text]
        result = subprocess.run(cmd, capture_output=True, text=True)
        path = result.stdout.strip()
    elif FILE_PICKER == "osascript":
        if is_dir:
            script = f'tell app "Finder" to POSIX path of (choose folder with prompt "{prompt_text}" default location POSIX file "{LAST_BROWSED_DIR}")'
        else:
            script = f'tell app "Finder" to POSIX path of (choose file with prompt "{prompt_text}" default location POSIX file "{LAST_BROWSED_DIR}")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
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
        path = filedialog.askdirectory(initialdir=LAST_BROWSED_DIR, title=prompt_text) if is_dir else filedialog.askopenfilename(initialdir=LAST_BROWSED_DIR, title=prompt_text)
        root.destroy()
        path = path or ""

    if path and os.path.exists(path):
        LAST_BROWSED_DIR = os.path.dirname(path) if os.path.isfile(path) else path
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
            else:
                print(YELLOW + "[-] Browse cancelled. Please type the path or try again." + RESET)
                continue
        elif user_input:
            path_to_check = user_input

        if path_to_check is not None:
            resolved = expand_path(path_to_check)
            if os.path.exists(resolved):
                return resolved
            else:
                print(RED + f"[-] ERROR: Path '{path_to_check}' does not exist. Please try again." + RESET)

def copy_and_lf(src, dst):
    with open(src, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    content = content.replace('\r\n', '\n')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    if os.access(src, os.X_OK):
        os.chmod(dst, 0o755)

# --- Configuration ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates", "out_of_the_box")
STAGING_DIR = os.path.join(ROOT_DIR, "_build_stage_")
TESTLAB_DIR = os.path.join(TEMPLATE_DIR, "statics", "testlab")
PROFILES_FILE = os.path.join(ROOT_DIR, ".builder_profiles.json")

def print_banner():
    print(CYAN + "=" * 60)
    print("       WELCOME TO INDIGRADER SUBMISSION-ONLY BUILDER")
    print("=" * 60)
    print("This builder sets up a distribution & submission mechanism")
    print("without the automatic grader.")
    print("=" * 60 + RESET)
    resp = input(YELLOW + "Press [ENTER] to continue, or type 'q' to quit: " + RESET).strip().lower()
    if resp in ['q', 'quit', 'exit']:
        sys.exit(0)
    print()

def main():
    if not os.path.exists(TEMPLATE_DIR):
        print(RED + f"[-] ERROR: Template directory not found at {TEMPLATE_DIR}" + RESET)
        sys.exit(1)

    print_banner()

    # --- 1. Gather Metadata ---
    course_id = input(CYAN + "Enter Course ID [DUMMY101]: " + RESET).strip().upper() or "DUMMY101"
    
    profiles = {}
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r") as f:
                profiles = json.load(f)
        except Exception:
            pass
            
    profile = profiles.get(course_id, {})
    if profile:
        print(GREEN + f"[*] Found saved profile for {course_id}. Press Enter to use saved defaults." + RESET)

    def_lab = profile.get("lab_name", "L1")
    while True:
        lab_name = input(CYAN + f"Enter Lab Name [{def_lab}]: " + RESET).strip().upper() or def_lab
        conflict_dir = os.path.join(ROOT_DIR, "Labs", f"packageIG_{lab_name}")
        conflict_zip = os.path.join(ROOT_DIR, "Labs", f"packageIG_{lab_name}.zip")
        if os.path.exists(conflict_dir) or os.path.exists(conflict_zip):
            print(RED + f"[-] Conflict: packageIG_{lab_name} already exists in Labs/!" + RESET)
            overwrite = input(YELLOW + "Do you want to overwrite it? (y/N): " + RESET).strip().lower()
            if overwrite == 'y':
                break
        else:
            break
    
    def_ip = profile.get("server_ip", "127.0.0.1")
    server_ip = input(CYAN + f"Enter Lab Server IP [{def_ip}]: " + RESET).strip() or def_ip
    
    def_sub = profile.get("subnet", "127.0.0.")
    subnet_str = input(CYAN + f"Enter Allowed Subnets (comma-separated) [{def_sub}]: " + RESET).strip() or def_sub
    allowed_subnets = [s.strip() for s in subnet_str.split(",") if s.strip()]
    
    default_date = datetime.now().strftime("%Y-%m-%d")
    date_str = input(CYAN + f"Enter Date (YYYY-MM-DD) [{default_date}]: " + RESET).strip() or default_date
    
    def_time = profile.get("start_time", "1400")
    start_time = input(CYAN + f"Enter Start Time (2400 format) [{def_time}]: " + RESET).strip() or def_time
    
    def_dur = profile.get("duration_mins", "120")
    duration_mins = int(input(CYAN + f"Enter Standard Duration in minutes [{def_dur}]: " + RESET).strip() or def_dur)
    
    def_pwd = profile.get("pwd_extra", "30")
    pwd_extra = int(input(CYAN + f"Enter PWD Extra Time in minutes [{def_pwd}]: " + RESET).strip() or def_pwd)
    
    start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H%M")
    end_dt = start_dt + timedelta(minutes=duration_mins)

    print()
    def_students = profile.get("students_path", "")
    students_path = get_path_input("Path to students.txt", is_dir=False, allow_blank=False, default_val=def_students)
    
    def_pwd_path = profile.get("pwd_path", "")
    pwd_path = get_path_input("Path to pwd_students.txt", is_dir=False, allow_blank=True, default_val=def_pwd_path)

    # Submission-Only Specific Inputs
    print(CYAN + "\n--- Submission-Only Lab Artifacts ---" + RESET)
    starter_folder = get_path_input("Path to starter folder (e.g., Lab-2/)", is_dir=True, allow_blank=False, default_val="")
    lectures_folder = get_path_input("Path to lectures folder", is_dir=True, allow_blank=False, default_val="")
    submissions_zip = get_path_input("Path to previous submissions zip", is_dir=False, allow_blank=False, default_val="")
    set_up_script = get_path_input("Path to set-up-script", is_dir=False, allow_blank=False, default_val="")
    
    # Update and save profile
    profile.update({
        "lab_name": lab_name,
        "server_ip": server_ip,
        "subnet": subnet_str,
        "start_time": start_time,
        "duration_mins": str(duration_mins),
        "pwd_extra": str(pwd_extra),
        "students_path": students_path,
        "pwd_path": pwd_path,
    })
    profiles[course_id] = profile
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        print(YELLOW + f"[-] Warning: Could not save profile: {e}" + RESET)

    # --- 2. Setup Staging Area ---
    print(CYAN + "\n[*] Assembling lab environment in staging area..." + RESET)
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    shutil.copytree(TEMPLATE_DIR, STAGING_DIR)

    # Clean out unused template testcases
    shutil.rmtree(os.path.join(STAGING_DIR, "testcases"), ignore_errors=True)
    
    # Copy admin tools, stop.sh, start.sh, and docs from root to staging area
    admin_src = os.path.join(ROOT_DIR, ".admin")
    docs_src = os.path.join(ROOT_DIR, "docs")
    stop_src = os.path.join(ROOT_DIR, "stop.sh")
    start_src = os.path.join(ROOT_DIR, "start.sh")
    
    if os.path.exists(admin_src):
        shutil.copytree(admin_src, os.path.join(STAGING_DIR, ".admin"))
    if os.path.exists(docs_src):
        shutil.copytree(docs_src, os.path.join(STAGING_DIR, "docs"))
    if os.path.exists(stop_src):
        shutil.copy2(stop_src, os.path.join(STAGING_DIR, "stop.sh"))
    if os.path.exists(start_src):
        shutil.copy2(start_src, os.path.join(STAGING_DIR, "start.sh"))

    # --- 3. Write config.json ---
    config_path = os.path.join(STAGING_DIR, "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    
    config["lab_name"] = lab_name
    config["start_time"] = start_dt.isoformat()
    config["end_time"] = end_dt.isoformat()
    config["allowed_subnets"] = allowed_subnets
    config["questions"] = ["Q1"]  # Default generic question for submission
    
    config["Q1"] = {
        "full_marks": 0,
        "timeout": 5,
        "memory_cap_mb": 512,
        "evaluator": None,
        "makefile": False,
        "ext": "ipynb"
    }
        
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

    # --- 4. Process Student Lists ---
    if os.path.exists(students_path):
        shutil.copy2(students_path, os.path.join(STAGING_DIR, "students.txt"))
    if pwd_path and os.path.exists(pwd_path):
        shutil.copy2(pwd_path, os.path.join(STAGING_DIR, "pwd_students.txt"))
    else:
        open(os.path.join(STAGING_DIR, "pwd_students.txt"), 'w').close()

    # --- 5. Template the Client Tool ---
    setup_sh_path = os.path.join(STAGING_DIR, "clients", "setup.sh")
    if os.path.exists(setup_sh_path):
        with open(setup_sh_path, "r") as f:
            setup_content = f.read()
        setup_content = setup_content.replace('COURSE_NAME_HERE', course_id)
        setup_content = setup_content.replace('SERVER_IP_HERE', server_ip)
        with open(setup_sh_path, "w") as f:
            f.write(setup_content)

    # --- 6. Assemble Statics ---
    statics_lab_dir = os.path.join(STAGING_DIR, "statics", lab_name)
    os.makedirs(statics_lab_dir, exist_ok=True)
    
    # 6a. Copy submit.sh
    src_submit = os.path.join(TESTLAB_DIR, "submit.sh")
    if os.path.exists(src_submit):
        copy_and_lf(src_submit, os.path.join(statics_lab_dir, "submit.sh"))
            
    # Include the student_workflow.md guide in the starter kit as README.md
    student_workflow_src = os.path.join(ROOT_DIR, "docs", "student_workflow.md")
    if os.path.exists(student_workflow_src):
        shutil.copy2(student_workflow_src, os.path.join(statics_lab_dir, "README.md"))
            
    # 6b. Copy config.json to .ig_course in statics
    ig_course_dir = os.path.join(statics_lab_dir, ".ig_course")
    os.makedirs(ig_course_dir, exist_ok=True)
    shutil.copy2(config_path, os.path.join(ig_course_dir, "config.json"))
    
    # 6c. Copy Custom Lab Artifacts
    # lectures/
    shutil.copytree(lectures_folder, os.path.join(statics_lab_dir, "lectures"))
    
    # previous submissions zip
    shutil.copy2(submissions_zip, os.path.join(statics_lab_dir, "previous_submissions.zip"))
    
    # init script
    copy_and_lf(set_up_script, os.path.join(statics_lab_dir, "set-up-script"))
    
    # starter folder renamed to CS25B0XX
    student_dummy_dir = os.path.join(statics_lab_dir, "CS25B0XX")
    shutil.copytree(starter_folder, student_dummy_dir)

    # Ensure statics has a zip
    shutil.make_archive(os.path.join(STAGING_DIR, "statics", lab_name), 'zip', root_dir=os.path.join(STAGING_DIR, "statics"), base_dir=lab_name)
    
    # Remove the unzipped testlab so it doesn't get deployed as a lab
    shutil.rmtree(os.path.join(STAGING_DIR, "statics", "testlab"), ignore_errors=True)
    
    # --- 7. Package Deployment Zip ---
    print(CYAN + "\n[*] Packaging deployment zip..." + RESET)
    zip_filename = f"packageIG_{lab_name}"
    
    # Create Labs directory
    labs_dir = os.path.join(ROOT_DIR, "Labs")
    os.makedirs(labs_dir, exist_ok=True)
    
    zip_filepath = os.path.join(labs_dir, zip_filename)
    
    # Instead of deleting, rename staging dir to the package name inside Labs
    final_dir = os.path.join(labs_dir, zip_filename)
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    os.rename(STAGING_DIR, final_dir)

    # Make archive from final_dir to preserve folder structure in zip
    shutil.make_archive(zip_filepath, 'zip', root_dir=labs_dir, base_dir=zip_filename)

    print(GREEN + f"\n[+] Success! {zip_filename}.zip and {zip_filename}/ folder have been generated in Labs/." + RESET)
    print(CYAN + "[*] You can inspect the folder for last minute checks, and transfer the zip to the lab server." + RESET)

if __name__ == "__main__":
    main()
