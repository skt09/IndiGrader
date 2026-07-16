# Student Workflow

This document outlines the standard operational sequence for a student utilizing the IndiGrader platform during a lab session.

## 1. Initial Tool Installation

Prior to the first lab session, the student executes the provided setup script:

```bash
bash setup.sh
```

This script installs the `ig` command-line interface (CLI) and configures the environment with a course-specific alias (e.g., `CS101`) mapped to the designated server URL.

## 2. Initiating a Lab Session

To commence a lab, the student executes the fetch command via the course alias. For instance, to fetch a lab named `testlab`:

```bash
CS101 fetch testlab
```

This procedure performs the following operations:
- Retrieves the `testlab.zip` archive from the server.
- Registers the client's IP address with the server for session binding.
- Extracts the lab directory structure.
- Auto-detects or prompts for the student's roll number, renaming the template source directory accordingly (e.g., resolving `CS25B0XX` to `CS25B012`).

## 3. Local Development and Testing

The student navigates to their specific source directory (e.g., `cd testlab/CS25B012`) to implement their solution. The `ig` CLI tools (`ig check`, `ig submit`) maintain context awareness and can be invoked from any subdirectory within the lab structure.

To evaluate code against the local public test cases, the student executes:

```bash
ig check
```

This command runs the grading engine locally, bypassing sandbox constraints, to provide immediate evaluation output.

## 4. Submitting for Server Evaluation

To submit code for formal evaluation, the student invokes:

```bash
ig submit
```

- The CLI compresses the relevant source files into an archive.
- The server validates the IP binding and enqueues the submission for processing.
- The client script polls the server and retrieves the evaluation verdict upon task completion.

## 5. Handling Late Submissions

If a submission is attempted after the configured deadline has elapsed, the `ig submit` command identifies the state locally.
- The execution pauses, displaying a warning regarding late submission policies.
- Explicit confirmation (`yes/no`) is required to proceed.
- Upon confirmation, the submission is transmitted and stored in the server's `late_submissions` directory for administrative review. Evaluation results are not returned to the client in this state.

## 6. Reviewing Submission History

Students may retrieve the evaluation history for a specific question using the history command:

```bash
ig history 1
```

This returns a log of prior submissions for Question 1, detailing the Serial Number (SN), timestamp, and awarded score for each attempt. To revert to a previous code state, the student inputs the target Serial Number when prompted. The CLI then retrieves and restores the corresponding source file from the server to the local filesystem.
