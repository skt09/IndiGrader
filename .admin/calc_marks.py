#!/usr/bin/env python3
import os
import csv
from datetime import datetime

# Run this from the root of the extracted lab (where submissions/ is)
SUBMISSIONS_DIR = "submissions"
OUTPUT_FILE = "final_grades.csv"

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

def main():
    if not os.path.exists(SUBMISSIONS_DIR):
        print(f"[-] ERROR: '{SUBMISSIONS_DIR}' folder not found.")
        print("Please run this script from the root of the lab directory.")
        return

    all_students = set()
    if os.path.exists("students.txt"):
        with open("students.txt", "r") as f:
            for line in f:
                parts = line.strip().split(',')
                if parts:
                    roll = parts[0].strip().split()[0]
                    if roll:
                        all_students.add(roll)
    else:
        print("[-] Warning: students.txt not found. Absent students will not be recorded.")

    grades = {s: {} for s in all_students} # Prepopulate with all students
    questions_found = set()

    for q_dir in os.listdir(SUBMISSIONS_DIR):
        q_path = os.path.join(SUBMISSIONS_DIR, q_dir)
        if not os.path.isdir(q_path):
            continue
            
        questions_found.add(q_dir)
        
        for roll_dir in os.listdir(q_path):
            student_path = os.path.join(q_path, roll_dir)
            if not os.path.isdir(student_path):
                continue
                
            marks_file = os.path.join(student_path, "marks.txt")
            if os.path.exists(marks_file):
                mark, _ = get_highest_mark(marks_file)
                if mark >= 0:
                    if roll_dir not in grades:
                        grades[roll_dir] = {}
                    grades[roll_dir][q_dir] = mark

    if not grades:
        print("[-] No grades found in submissions.")
        return

    questions = sorted(list(questions_found))
    
    print(f"[*] Calculating marks for {len(grades)} students across {len(questions)} questions...")

    with open(OUTPUT_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Header
        header = ["Roll_Number"] + questions + ["Total_Marks"]
        writer.writerow(header)
        
        for roll in sorted(grades.keys()):
            row = [roll]
            total = 0
            for q in questions:
                mark = grades[roll].get(q, 0.0)
                row.append(mark)
                if mark != -1.0:
                    total += mark
            row.append(total)
            writer.writerow(row)

    print(f"[+] Grades successfully calculated and saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
