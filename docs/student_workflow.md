# Student Workflow

This document outlines the standard lab sequence for a student using IndiGrader.

## 1. Initial Tool Installation (Once per course)
The student executes the setup script provided by the instructor:
```bash
bash setup.sh
```
This installs the `ig` CLI tool and establishes the server URL alias for the course (e.g., creating a command alias `CS101`).

## 2. Starting a Lab
When a lab begins, the student runs the fetch command. For example, if the lab is named `testlab` and the course alias is `CS101`:
```bash
CS101 fetch testlab
```
This command performs several automated tasks:
- Downloads the `testlab.zip` package from the server.
- Registers the student's IP address on the server to prevent impersonation.
- Extracts the lab material.
- Prompts for the student's roll number if it cannot be auto-detected, and renames the template source directory to match their actual roll number (e.g., renaming `CS25B0XX` to `CS25B012`).

## 3. Writing and Testing Code
The student navigates into their newly created folder (e.g., `cd testlab/CS25B012`) and writes their solution for the questions.
*Note: The `ig` CLI commands (`ig check`, `ig submit`) are context-aware and can be executed from anywhere within your lab folder structure.*

To verify their code locally against the public test cases, they simply run:
```bash
ig check
```
This executes the unified grading engine locally without sandbox constraints, providing immediate feedback.

## 4. Submitting for Evaluation
Once confident, the student submits their code to the server's asynchronous queue:
```bash
ig submit
```
- The system automatically packages the active source files.
- The server validates the IP and accepts the submission into the queue.
- The script polls the server until the grading task is complete and then prints the detailed verdict.

## 5. Late Submissions
If a student attempts to submit after the lab deadline has passed, the `ig submit` script detects this locally.
- The script pauses and displays a strict warning that they are burning their single allowed late submission and that marks will not be considered.
- It prompts for explicit confirmation (`yes/no`).
- If confirmed, the submission is saved to the server's shadow `late_submissions` directory for instructor reference. No grades or results are printed to the student.

## 6. Reviewing History
Students can fetch a detailed history of all their grading attempts for a specific question:
```bash
ig history 1
```
This command provides a comprehensive ledger of all previous submissions for Question 1. It displays the Serial Number (SN), timestamp, and the marks obtained for each attempt. If a student wants to restore a previous version of their code, they can simply enter the corresponding Serial Number when prompted, and the CLI will instantly download and restore that exact source file to their local machine.
