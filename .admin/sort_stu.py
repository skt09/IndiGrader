#!/usr/bin/env python3
import os
import shutil
import glob

SUBMISSIONS_DIR = "submissions"
OUTPUT_DIR = "highest_submissions_by_stu"

def get_highest_mark_timestamp(marks_file):
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
                        if mark > highest_mark or (mark == highest_mark and ts_str > (best_timestamp or "")):
                            highest_mark = mark
                            best_timestamp = ts_str
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error reading {marks_file}: {e}")
    return best_timestamp

def main():
    if not os.path.exists(SUBMISSIONS_DIR):
        print(f"[-] ERROR: '{SUBMISSIONS_DIR}' folder not found.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0

    all_students = set()
    if os.path.exists("students.txt"):
        with open("students.txt", "r") as f:
            for line in f:
                parts = line.strip().split(',')
                if parts:
                    roll = parts[0].strip().split()[0]
                    if roll:
                        all_students.add(roll)
                        
    # Create empty folders for all known students upfront
    for roll in all_students:
        os.makedirs(os.path.join(OUTPUT_DIR, roll), exist_ok=True)

    print(f"[*] Scanning submissions and sorting by Student...")

    for q_dir in os.listdir(SUBMISSIONS_DIR):
        q_path = os.path.join(SUBMISSIONS_DIR, q_dir)
        if not os.path.isdir(q_path):
            continue
            
        for roll_dir in os.listdir(q_path):
            student_path = os.path.join(q_path, roll_dir)
            if not os.path.isdir(student_path):
                continue
                
            marks_file = os.path.join(student_path, "marks.txt")
            if not os.path.exists(marks_file):
                continue
                
            best_ts = get_highest_mark_timestamp(marks_file)
            if not best_ts:
                continue
                
            # Create student output dir
            stu_out_dir = os.path.join(OUTPUT_DIR, roll_dir)
            os.makedirs(stu_out_dir, exist_ok=True)

            # Find source file
            pattern = os.path.join(student_path, f"{q_dir}_{best_ts}.*")
            matching_files = glob.glob(pattern)
            
            if matching_files:
                src_file = matching_files[0]
                ext = os.path.splitext(src_file)[1]
                dst_file = os.path.join(stu_out_dir, f"{q_dir}{ext}")
                shutil.copy2(src_file, dst_file)
                count += 1
            else:
                print(f"[-] Warning: Best submission for {roll_dir} in {q_dir} (TS: {best_ts}) not found.")

    print(f"[+] Successfully extracted {count} submissions into '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()
