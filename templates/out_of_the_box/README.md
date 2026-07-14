# Out-of-the-Box Template

This is the standard, production-ready grading template for IndiGrader. It provides a full environment designed for evaluating typical programming assignments (like C, C++, Python, and AWK) relying on standard input/output comparisons, without requiring custom evaluators.

## 1. Prerequisites
Ensure the server machine has the following installed:
- Python 3.9+
- Redis Server (`sudo apt install redis-server`)
- Firejail (`sudo apt install firejail`)

## 2. Server Installation & Offline Deployment
Because strict lab environments often lack internet access, the recommended workflow is to prepare the system offline:
1. **Prepare Locally:** Configure `config.json`, and set up your `testcases/` and `statics/` folders on your personal machine within this template folder.
2. **Package & Transfer:** Zip this entire configured `out_of_the_box` directory and transfer it to the lab's main server.
3. **Install Dependencies:** On the lab server, extract the package and install the requirements:
```bash
# It is highly recommended to create a virtual environment in your home directory.
# (Note: This setup is only required on the first day if not set up earlier):
python3 -m venv ~/.venv
source ~/.venv/bin/activate

pip install -r requirements.txt
```
*(Note: If the lab server is completely air-gapped, you may need to download the pip packages offline beforehand).*

## 3. Configuration
1. **`config.json`**: Edit the root configuration file to define your lab's parameters.
   - `start_time` / `end_time`: Enforces strict submission deadlines.
   - `allowed_subnet`: e.g., `"192.168.1."` to restrict access strictly to the lab's local network.
   - `questions`: List the questions (e.g., `["Q1", "Q2"]`) and their constraints.
   - **Makefile Projects**: To support multi-file projects needing a `Makefile`, set `"makefile": true`. The engine will run `make` on the student's submission. Use `"executable_name": "target_name"` to define what binary the `make` command produces (defaults to the question name, e.g., `Q1`).
2. **`pwd_students.txt`**: Add the roll numbers of Persons with Disabilities (PwD) students to this file, one per line. This grants them an exemption from the strict lab `end_time` deadline.

## 4. Preparing the Test Cases
IndiGrader supports up to 100 test cases per question, numbered `00` to `99` (e.g., `input00.txt`, `input99.txt`). 

> [!NOTE]
> **Weightage:** All test cases carry equal weightage. If you want a specific scenario to carry more weight, simply duplicate that test case.

**Public vs. Private Test Cases:**
There are two distinct and independent testcase directories:
1. **Server-Side (`testcases/`):** Contains the test cases used for final grading. These are typically hidden private cases.
2. **Student-Side (`statics/testlab/testcases/`):** Contains only the *public* test cases for local verification.

### Input Modes (The Strict Separation Rule)
IndiGrader automatically detects how to execute a student's program based strictly on how you name and structure the items inside the `input/` directory.

**1. Stdin-Only Mode (Default)**
If your test case only requires standard input, provide a `.txt` file named `input##.txt`.

**2. Arg-Only Mode**
If your test case requires Command Line Arguments (and NO standard input), provide a `.txt` file named `args##.txt`. The contents of this file are read and passed directly to the student's executable as arguments.

**3. Hybrid/Directory Mode (Used for File IO & CLA)**
If a test case requires external files (like a `data.csv`), create a directory named `input##/`. Everything inside this directory will be copied securely into the sandbox. The system automatically looks for `args.txt` and `stdin.txt` inside this directory to handle execution parameters.

### Global Static Files
If multiple test cases share the exact same files, place them in a `static/` directory inside the question's testcase folder (e.g., `testcases/Q1/static/`). These files are injected into *every* sandbox execution for that question before compilation, preventing folder bloat.

**Important Note:** When using the `builder.py` wizard, it will prompt you for a single path to your static files folder. Therefore, you MUST keep all your static files for a question together in a single directory on your local machine before running the builder. During evaluation, all contents from inside this single directory are aggressively dumped into the root of the sandbox environment.

> [!TIP]
> **LeetCode-Style Assignments**
> You can use the `static/` folder to simulate a LeetCode-style environment where the student only implements a single function.
> 1. Set `"makefile": true` in your `config.json`.
> 2. Place your official, hidden `main.c` (or `main.cpp`) and any required headers inside the `testcases/Q1/static/` directory on the server.
> 3. Provide the student with a dummy `main.c`, a `solution.c` template, and a `Makefile`.
> 
> When the student submits, the server will aggressively overwrite their `main.c` with your trusted version from the `static/` directory before running `make`. This guarantees they cannot bypass the tests by tampering with the `main.c` file!

## 5. Preparing the Student Starter Kit
Students download a zip file to start their lab. Prepare this inside the `statics/` folder.
1. Create a directory named after your lab (e.g., `statics/testlab/`).
2. Add the lab manual (`Problem-Statement.pdf`).
3. Add the execution scripts: `grade.sh`, `check.sh`, `submit.sh`.
4. Create the starter code:
   - For standard labs, create a dummy file (e.g., `CS25B0XX/Q1.c`).
   - For **Makefile projects**, you MUST create a directory (e.g., `CS25B0XX/Q1/`) and place the `Makefile` inside it.
5. Create a subset of public test cases in `testcases/`.
6. Create the hidden configuration directory `.ig_course/` and copy the `config.json` inside it.
7. Zip the directory to create the downloadable starter kit:
```bash
cd statics
zip -qr testlab.zip testlab
```

> [!IMPORTANT]
> **Why do I have to zip it manually?** 
> You MUST manually zip the starter kit folder before starting the server, otherwise the `ig fetch` command will fail because the server won't have a `.zip` file to serve!

## 6. Distributing the CLI Tool
1. Edit `clients/setup.sh`. Update the `COURSE_ID` and `DEFAULT_SERVER_URL` at the top of the file.
2. Provide students with the following command to download and install the client tool directly:
```bash
curl http://<server-ip>:<port>/clients/setup.sh | bash
```

## 7. Starting the System
Instead of starting the components manually, we recommend using the automated scripts generated by the builder:

To start the Celery worker and FastAPI server in the background:
```bash
chmod +x start.sh
./start.sh
```

To safely shut down the system and ensure all queued gradings are completed before exiting:
```bash
./stop.sh
```
