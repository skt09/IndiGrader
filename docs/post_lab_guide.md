# Post-Lab Guide

This guide outlines the procedures for processing student submissions after a lab session has concluded and the server has been safely shut down.

## Post-Lab Processing Utilities

The `.admin/` directory within the generated lab package contains utilities for processing data in the `submissions/` directory.

### A. Grade Aggregation (`calc_marks.py`)

This script aggregates the highest scores achieved by each student into a consolidated CSV file.

```bash
python3 .admin/calc_marks.py
```

**Functionality:**
- Parses `students.txt` to ensure an entry exists for all registered students.
- Assigns a score of `0.0` to absent students or those without valid submissions.
- Outputs the results to `final_grades.csv` in the root directory.

### B. Plagiarism Check Preparation (`sort_q.py`)

This script reorganizes submissions to facilitate plagiarism detection (e.g., using MOSS).

```bash
python3 .admin/sort_q.py
```

**Functionality:**
- Iterates through the submission records and isolates the highest-scoring source file for each student.
- Copies the identified files into a flat directory structure structured by question (e.g., `highest_submissions_by_q/Q1/CS25B001.c`).

### C. Manual Review Preparation (`sort_stu.py`)

This script organizes submissions into a student-centric directory structure for manual review by teaching assistants.

```bash
python3 .admin/sort_stu.py
```

**Functionality:**
- Groups the highest-scoring files by student roll number (e.g., `highest_submissions_by_stu/CS25B001/Q1.c`).
- Ensures a directory is initialized for every student listed in `students.txt`, including those without submissions.
