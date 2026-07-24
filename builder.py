#!/usr/bin/env python3
import os
import sys
import shutil
import json
from datetime import datetime, timedelta

CYAN = '\033[1;36m'
GREEN = '\033[1;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
RESET = '\033[0m'

import subprocess
import platform

def _detect_file_picker():
    """Returns the available native file picker backend, or None."""
    def _cmd_exists(cmd):
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    if platform.system() == "Darwin":
        return "osascript"  # macOS — always available
    if _cmd_exists("zenity"):
        return "zenity"     # GNOME / Ubuntu
    if _cmd_exists("kdialog"):
        return "kdialog"    # KDE
    try:
        import tkinter  # noqa: F401
        return "tkinter"    # Fallback: Python built-in
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

# --- Configuration ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates", "out_of_the_box")
STAGING_DIR = os.path.join(ROOT_DIR, "_build_stage_")
TESTLAB_DIR = os.path.join(TEMPLATE_DIR, "statics", "testlab")
PROFILES_FILE = os.path.join(ROOT_DIR, ".builder_profiles.json")

def print_banner():
    print(CYAN + "=" * 60)
    print("       WELCOME TO INDIGRADER LAB BUILDER (Pre-Lab)")
    print("=" * 60)
    print("Before we begin, ensure you have your testcases ready.")
    print("See docs/setup_guide.md for naming conventions.")
    print("=" * 60 + RESET)
    resp = input(YELLOW + "Press [ENTER] to continue, or type 'q' to quit: " + RESET).strip().lower()
    if resp in ['q', 'quit', 'exit']:
        sys.exit(0)
    print()

def validate_testcases(tc_path, mode):
    """
    mode: 1 (Stdin: input##.txt), 2 (Args: args##.txt), 3 (Hybrid: input##/ dir)
    """
    if not os.path.exists(tc_path):
        print(RED + f"[-] ERROR: Testcase path '{tc_path}' does not exist." + RESET)
        return False
    
    # Check if they already provided input/ and output/ folders
    has_input_dir = os.path.isdir(os.path.join(tc_path, "input"))
    has_output_dir = os.path.isdir(os.path.join(tc_path, "output"))
    
    if has_input_dir and has_output_dir:
        in_path = os.path.join(tc_path, "input")
        out_path = os.path.join(tc_path, "output")
        in_files_list = os.listdir(in_path)
        out_files_list = os.listdir(out_path)
    else:
        in_path = tc_path
        out_path = tc_path
        files = os.listdir(tc_path)
        in_files_list = files
        out_files_list = files

    if not in_files_list or not out_files_list:
        print(RED + f"[-] ERROR: Testcase folder '{tc_path}' is empty or missing input/output files." + RESET)
        return False

    valid_count = 0
    for f in out_files_list:
        # Check Outputs
        if f.startswith("output") and f.endswith(".txt"):
            num = f[6:-4]
            
            if mode == 1: # Stdin
                expected_in = f"input{num}.txt"
                if expected_in not in in_files_list:
                    print(f"[-] ERROR: Found '{f}' but missing '{expected_in}' in input.")
                    return False
            elif mode == 2: # Args
                expected_in = f"args{num}.txt"
                if expected_in not in in_files_list:
                    print(f"[-] ERROR: Found '{f}' but missing '{expected_in}' in input.")
                    return False
            elif mode == 3: # Hybrid
                expected_in = f"input{num}"
                if expected_in not in in_files_list or not os.path.isdir(os.path.join(in_path, expected_in)):
                    print(f"[-] ERROR: Found '{f}' but missing directory '{expected_in}/' in input.")
                    return False
                    
            valid_count += 1

    if valid_count == 0:
        print(RED + f"[-] ERROR: No valid testcases found in '{tc_path}' for the selected mode." + RESET)
        return False

    return True

def copy_and_lf(src, dst):
    with open(src, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    content = content.replace('\r\n', '\n')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    if os.access(src, os.X_OK):
        os.chmod(dst, 0o755)

def copy_testcases_to_engine(src_folder, dest_root_folder, mode):
    """
    Copies testcases from src_folder to dest_root_folder/input/ and dest_root_folder/output/
    """
    in_dir = os.path.join(dest_root_folder, "input")
    out_dir = os.path.join(dest_root_folder, "output")
    os.makedirs(in_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    has_input_dir = os.path.isdir(os.path.join(src_folder, "input"))
    has_output_dir = os.path.isdir(os.path.join(src_folder, "output"))
    
    if has_input_dir and has_output_dir:
        for f in os.listdir(os.path.join(src_folder, "input")):
            src_item = os.path.join(src_folder, "input", f)
            if os.path.isdir(src_item):
                shutil.copytree(src_item, os.path.join(in_dir, f))
            else:
                shutil.copy2(src_item, os.path.join(in_dir, f))
                
        for f in os.listdir(os.path.join(src_folder, "output")):
            src_item = os.path.join(src_folder, "output", f)
            if os.path.isdir(src_item):
                shutil.copytree(src_item, os.path.join(out_dir, f))
            else:
                shutil.copy2(src_item, os.path.join(out_dir, f))
    else:
        for f in os.listdir(src_folder):
            src_item = os.path.join(src_folder, f)
            if f.startswith("output"):
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, os.path.join(out_dir, f))
                else:
                    shutil.copy2(src_item, os.path.join(out_dir, f))
            elif f.startswith("input") or f.startswith("args"):
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, os.path.join(in_dir, f))
                else:
                    shutil.copy2(src_item, os.path.join(in_dir, f))

def get_path_input(prompt_text, is_dir=False, allow_blank=False, default_val=""):
    while True:
        browse_hint = " (type 'b' to browse)" if FILE_PICKER else ""
        blank_hint = " (leave blank to skip)" if allow_blank and not default_val else ""
        default_hint = f" [{default_val}]" if default_val else ""
        user_input = input(CYAN + f"{prompt_text}{default_hint}{blank_hint}{browse_hint}: " + RESET).strip()
        
        if not user_input and default_val:
            return default_val
            
        if allow_blank and user_input == "":
            return ""
            
        if FILE_PICKER and user_input.lower() in ['b', 'browse']:
            path = _native_browse(prompt_text, is_dir=is_dir)
            if path:
                print(GREEN + f"[*] Selected: {path}" + RESET)
                return path
            else:
                print(YELLOW + "[-] Browse cancelled. Please type the path or try again." + RESET)
                continue
                
        if user_input:
            return user_input

def main():
    if not os.path.exists(TEMPLATE_DIR):
        print(RED + f"[-] ERROR: Template directory not found at {TEMPLATE_DIR}" + RESET)
        sys.exit(1)

    print_banner()

    # --- 1. Gather Metadata ---
    course_id = input(CYAN + "Enter Course ID [DUMMY101]: " + RESET).strip().upper() or "DUMMY101"
    
    # Load profile for course
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
    lab_name = input(CYAN + f"Enter Lab Name [{def_lab}]: " + RESET).strip().upper() or def_lab
    
    def_ip = profile.get("server_ip", "127.0.0.1")
    server_ip = input(CYAN + f"Enter Lab Server IP [{def_ip}]: " + RESET).strip() or def_ip
    
    def_sub = profile.get("subnet", "127.0.0.")
    subnet = input(CYAN + f"Enter Allowed Subnet [{def_sub}]: " + RESET).strip() or def_sub
    
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
    
    def_stmt = profile.get("global_prob_stmt", "")
    global_prob_stmt = get_path_input("Path to global problem statement PDF/MD/TXT", is_dir=False, allow_blank=True, default_val=def_stmt)

    num_q = int(input(CYAN + "\nNumber of Questions [1]: " + RESET).strip() or "1")
    
    # Update and save profile
    profile.update({
        "lab_name": lab_name,
        "server_ip": server_ip,
        "subnet": subnet,
        "start_time": start_time,
        "duration_mins": str(duration_mins),
        "pwd_extra": str(pwd_extra),
        "students_path": students_path,
        "pwd_path": pwd_path,
        "global_prob_stmt": global_prob_stmt
    })
    profiles[course_id] = profile
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        print(YELLOW + f"[-] Warning: Could not save profile: {e}" + RESET)

    questions_config = {}
    for i in range(1, num_q + 1):
        q_name = f"Q{i}"
        print(CYAN + f"\n--- Configuring {q_name} ---" + RESET)
        
        full_marks = float(input(CYAN + f"Full Marks for {q_name}: " + RESET).strip() or "100")
        timeout = float(input(CYAN + f"Timeout (seconds) for {q_name}: " + RESET).strip() or "5")
        mem_cap = int(input(CYAN + f"Memory Cap (MB) for {q_name}: " + RESET).strip() or "512")
        
        is_makefile = input(CYAN + f"Does {q_name} use a Makefile? (y/N): " + RESET).strip().lower() == 'y'
        
        print(CYAN + "Input Modes:")
        print("  1. Stdin-Only (input##.txt)")
        print("  2. Arg-Only (args##.txt)")
        print("  3. Hybrid/Directory (input##/ directory containing args.txt, stdin.txt, files)" + RESET)
        mode_str = input(CYAN + "Select mode (1/2/3): " + RESET).strip()
        mode = int(mode_str) if mode_str in ['1', '2', '3'] else 1
        
        while True:
            public_tc = get_path_input(f"Path to {q_name} PUBLIC testcases folder (Only for students!)", is_dir=True, allow_blank=False)
            if validate_testcases(public_tc, mode):
                break
                
        while True:
            private_tc = get_path_input(f"Path to {q_name} PRIVATE testcases folder (Only for server!)", is_dir=True, allow_blank=False)
            if validate_testcases(private_tc, mode):
                break
                
        static_folder = get_path_input(f"Path to global 'static' files folder for {q_name}", is_dir=True, allow_blank=True)
        starter_code = get_path_input(f"Path to starter code for {q_name} (File if normal, Folder if Makefile)", is_dir=is_makefile, allow_blank=True)

        if not is_makefile and not starter_code:
            ext = input(CYAN + f"No starter code provided. Expected file extension for {q_name} (e.g., c, cpp, py, sh, awk): " + RESET).strip().lstrip('.')
            if not ext:
                ext = 'c'
        else:
            ext = ''

        questions_config[q_name] = {
            "full_marks": full_marks,
            "timeout": timeout,
            "memory_cap_mb": mem_cap,
            "public_tc": public_tc,
            "private_tc": private_tc,
            "static_folder": static_folder,
            "starter": starter_code,
            "is_makefile": is_makefile,
            "mode": mode,
            "ext": ext
        }

    # --- 2. Setup Staging Area ---
    print(CYAN + "\n[*] Assembling lab environment in staging area..." + RESET)
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    shutil.copytree(TEMPLATE_DIR, STAGING_DIR)

    # Clean out the template testcases and statics
    shutil.rmtree(os.path.join(STAGING_DIR, "testcases"))
    os.makedirs(os.path.join(STAGING_DIR, "testcases"))
    
    # Copy admin tools, stop.sh, start.sh, and docs from root to staging area so they travel with the package
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
    config["allowed_subnets"] = [subnet]
    config["questions"] = [f"Q{i}" for i in range(1, num_q + 1)]
    
    for i in range(1, num_q + 1):
        q_name = f"Q{i}"
        config[q_name] = {
            "full_marks": questions_config[q_name]["full_marks"],
            "timeout": questions_config[q_name]["timeout"],
            "memory_cap_mb": questions_config[q_name]["memory_cap_mb"],
            "evaluator": None,
            "makefile": questions_config[q_name]["is_makefile"],
            "ext": questions_config[q_name]["ext"]
        }
        if questions_config[q_name]["is_makefile"]:
            config[q_name]["executable_name"] = q_name
        
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

    # --- 6. Assemble Statics & Testcases ---
    statics_lab_dir = os.path.join(STAGING_DIR, "statics", lab_name)
    os.makedirs(statics_lab_dir, exist_ok=True)
    
    # 6a. Copy vital scripts from testlab template to new statics folder
    for script in ["check.sh", "submit.sh", "grade.sh"]:
        src_script = os.path.join(TESTLAB_DIR, script)
        if os.path.exists(src_script):
            copy_and_lf(src_script, os.path.join(statics_lab_dir, script))
            
    # Include the student_workflow.md guide in the starter kit as README.md
    student_workflow_src = os.path.join(ROOT_DIR, "docs", "student_workflow.md")
    if os.path.exists(student_workflow_src):
        shutil.copy2(student_workflow_src, os.path.join(statics_lab_dir, "README.md"))
            
    # 6b. Copy config.json to .ig_course in statics
    ig_course_dir = os.path.join(statics_lab_dir, ".ig_course")
    os.makedirs(ig_course_dir, exist_ok=True)
    shutil.copy2(config_path, os.path.join(ig_course_dir, "config.json"))
    
    # Global Problem statement
    if global_prob_stmt and os.path.exists(global_prob_stmt):
        shutil.copy2(global_prob_stmt, statics_lab_dir)
    
    # 6c. Setup dummy student directory
    student_dummy_dir = os.path.join(statics_lab_dir, "CS25B0XX")
    os.makedirs(student_dummy_dir, exist_ok=True)
    
    for q_name, conf in questions_config.items():
        # Testcases - Server side (PRIVATE ONLY)
        server_q_dir = os.path.join(STAGING_DIR, "testcases", q_name)
        copy_testcases_to_engine(conf["private_tc"], server_q_dir, conf["mode"])
        
        # Testcases - Student side (PUBLIC ONLY)
        student_tc_dir = os.path.join(statics_lab_dir, "testcases", q_name)
        copy_testcases_to_engine(conf["public_tc"], student_tc_dir, conf["mode"])
        
        # Static files (LeetCode style) -> Copy to BOTH Server and Student
        if conf["static_folder"] and os.path.exists(conf["static_folder"]):
            server_static_dest = os.path.join(server_q_dir, "static")
            student_static_dest = os.path.join(student_tc_dir, "static")
            shutil.copytree(conf["static_folder"], server_static_dest)
            shutil.copytree(conf["static_folder"], student_static_dest)
            
        # Starter Code
        if conf["is_makefile"]:
            q_folder = os.path.join(student_dummy_dir, q_name)
            if conf["starter"] and os.path.isdir(conf["starter"]):
                shutil.copytree(conf["starter"], q_folder)
            else:
                os.makedirs(q_folder, exist_ok=True)
                with open(os.path.join(q_folder, "Makefile"), "w") as f:
                    f.write(f"all:\n\tgcc -o {q_name} main.c\n")
                with open(os.path.join(q_folder, "main.c"), "w") as f:
                    f.write("#include <stdio.h>\n\nint main() {\n    // Code here\n    return 0;\n}\n")
        else:
            if conf["starter"] and os.path.isfile(conf["starter"]):
                # Preserve the extension of the provided starter file
                _, actual_ext = os.path.splitext(conf["starter"])
                starter_dest = os.path.join(student_dummy_dir, f"{q_name}{actual_ext}")
                copy_and_lf(conf["starter"], starter_dest)
            else:
                # Use the prompted extension and generate a minimal template
                starter_dest = os.path.join(student_dummy_dir, f"{q_name}.{conf['ext']}")
                with open(starter_dest, "w") as f:
                    if conf['ext'] == 'c':
                        f.write("#include <stdio.h>\n\nint main() {\n    // Code here\n    return 0;\n}\n")
                    elif conf['ext'] == 'cpp':
                        f.write("#include <iostream>\nusing namespace std;\n\nint main() {\n    // Code here\n    return 0;\n}\n")
                    elif conf['ext'] == 'py':
                        f.write("# Write your Python code here\n")
                    elif conf['ext'] in ['sh', 'awk']:
                        f.write("# Write your script here\n")
                    else:
                        f.write("// Write your code here\n")

    # Ensure statics has a zip
    shutil.make_archive(os.path.join(STAGING_DIR, "statics", lab_name), 'zip', root_dir=os.path.join(STAGING_DIR, "statics"), base_dir=lab_name)
    
    # Remove the unzipped testlab so it doesn't get deployed as a lab
    shutil.rmtree(os.path.join(STAGING_DIR, "statics", "testlab"))
    
    # --- 7. Package Deployment Zip ---
    print(CYAN + "\n[*] Packaging deployment zip..." + RESET)
    zip_filename = f"packageIG_{lab_name}"
    
    # Create Labs directory
    labs_dir = os.path.join(ROOT_DIR, "Labs")
    os.makedirs(labs_dir, exist_ok=True)
    
    zip_filepath = os.path.join(labs_dir, zip_filename)
    shutil.make_archive(zip_filepath, 'zip', STAGING_DIR)
    
    # Instead of deleting, rename staging dir to the package name inside Labs
    final_dir = os.path.join(labs_dir, zip_filename)
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    os.rename(STAGING_DIR, final_dir)

    print(GREEN + f"\n[+] Success! {zip_filename}.zip and {zip_filename}/ folder have been generated in Labs/." + RESET)
    print(CYAN + "[*] You can inspect the folder for last minute checks, and transfer the zip to the lab server." + RESET)

if __name__ == "__main__":
    main()
