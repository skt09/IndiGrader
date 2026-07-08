# IndiGrader Post-Lab Guide

This guide explains how to process student submissions and securely return files to students after you have safely shut down the lab server and downloaded the final folder.

## 1. Post-Lab Processing Utilities
Inside the `.admin/` directory of your extracted lab, you will find three automated Python utilities designed to process the `submissions/` directory.

### A. Calculating Grades (`calc_marks.py`)
Run this script to aggregate all highest scores into a single CSV.
```bash
python3 .admin/calc_marks.py
```
**Features:**
- It parses `students.txt` and guarantees that **every** student in your class gets a row in the CSV.
- Absent students, or students who submitted nothing, will automatically receive a `0.0`.
- It outputs `final_grades.csv` at the root.

### B. Extracting for MOSS (`sort_q.py`)
Run this script if you need to perform plagiarism checking.
```bash
python3 .admin/sort_q.py
```
- It scans the submissions, isolates the single highest-scoring source file for each student, and copies them into `highest_submissions_by_q/Q1/`.
- This creates a perfect flat directory of `CS25B001.c`, `CS25B002.c`, etc., which is ideal for uploading to MOSS.

### C. Extracting for TA Review (`sort_stu.py`)
Run this script if TAs need to manually review the code.
```bash
python3 .admin/sort_stu.py
```
- It organizes the highest-scoring files by student folder (e.g., `highest_submissions_by_stu/CS25B001/Q1.c`).
- It guarantees that a folder is created for every student in `students.txt`, even if it is completely empty.


