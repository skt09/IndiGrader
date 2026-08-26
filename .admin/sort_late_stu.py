#!/usr/bin/env python3
import os
import shutil
import glob

LATE_SUBMISSIONS_DIR = "late_submissions"
OUTPUT_DIR = "late_submissions_by_stu"

def main():
    if not os.path.exists(LATE_SUBMISSIONS_DIR):
        print(f"[-] ERROR: '{LATE_SUBMISSIONS_DIR}' folder not found.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0

    print(f"[*] Scanning late submissions and sorting by Student...")

    for q_dir in os.listdir(LATE_SUBMISSIONS_DIR):
        q_path = os.path.join(LATE_SUBMISSIONS_DIR, q_dir)
        if not os.path.isdir(q_path):
            continue
            
        for roll_dir in os.listdir(q_path):
            student_path = os.path.join(q_path, roll_dir)
            if not os.path.isdir(student_path):
                continue
                
            marks_file = os.path.join(student_path, "marks.txt")
            mark_entry = None
            if os.path.exists(marks_file):
                try:
                    with open(marks_file, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            last_line = lines[-1].strip()
                            parts = last_line.split(',')
                            if len(parts) == 2:
                                ts_str, mark_str = parts[0].strip(), parts[1].strip()
                                mark_entry = f"{q_dir}: {ts_str}, {mark_str}\n"
                except Exception as e:
                    print(f"Error reading {marks_file}: {e}")

            matching_files = [
                f for f in glob.glob(os.path.join(student_path, "*")) 
                if os.path.isfile(f) and not f.endswith("marks.txt") and not f.endswith(".log")
            ]
            
            if matching_files or mark_entry:
                stu_out_dir = os.path.join(OUTPUT_DIR, roll_dir)
                os.makedirs(stu_out_dir, exist_ok=True)
                
                if matching_files:
                    src_file = matching_files[0]
                    ext = os.path.splitext(src_file)[1]
                    dst_file = os.path.join(stu_out_dir, f"{q_dir}{ext}")
                    shutil.copy2(src_file, dst_file)
                    count += 1
                
                if mark_entry:
                    consolidated_marks = os.path.join(stu_out_dir, "marks.txt")
                    with open(consolidated_marks, 'a') as cf:
                        cf.write(mark_entry)
            else:
                print(f"[-] Warning: No valid files or marks found for {roll_dir} in {q_dir}.")

    print(f"[+] Successfully extracted {count} late submissions into '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()
