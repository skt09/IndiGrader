# Setup Guide (For Instructors)

This guide outlines how to prepare the server and distribute the lab environment to students.

## 1. Prerequisites
Ensure the server machine has the following installed:
- Python 3.9+
- Redis Server (`sudo apt install redis-server`)
- Firejail (`sudo apt install firejail`)

## 2. Server Installation & Offline Deployment
Because strict lab environments often lack internet access, the recommended workflow is to prepare the system offline:
1. **Prepare Locally:** Clone the repository, configure `config.json`, and set up your `testcases/` and `statics/` folders on your personal machine.
2. **Package & Transfer:** Zip the entire configured `IndiGrader` directory and transfer it to the lab's main server.
3. **Install Dependencies:** On the lab server, extract the package and install the requirements:
```bash
pip install -r requirements.txt
```
*(Note: If the lab server is completely air-gapped, you may need to download the pip packages offline beforehand).*

## 3. Configuration
1. **`config.json`**: Edit the root configuration file to define your lab's parameters.
   - `start_time` / `end_time`: Enforces strict submission deadlines.
   - `allowed_subnet`: e.g., `"192.168.1."` to restrict access strictly to the lab's local network.
   - `questions`: List the questions (e.g., `["Q1", "Q2"]`) and their memory/timeout constraints.
2. **`pwd_students.txt`**: Add the roll numbers of Persons with Disabilities (PwD) students to this file, one per line. This grants them an exemption from the strict lab `end_time` deadline, allowing them extra time as per government mandate.

## 4. Preparing the Test Cases
IndiGrader supports up to 100 test cases per question, numbered `00` to `99` (e.g., `input00.txt`, `input99.txt`). 

> [!NOTE]
> **Weightage:** All test cases carry equal weightage. If you want a specific scenario to carry more weight, simply duplicate that test case.

**Public vs. Private Test Cases:**
There are two distinct and independent testcase directories:
1. **Server-Side (`testcases/`):** Contains the test cases used for final grading. These are typically hidden private cases. The instructor may choose whether or not to include the public test cases here; the two sets are completely independent. 
   > [!IMPORTANT]
   > The system does not reveal private case inputs, outputs, or diffs to students; they only receive a Pass/Fail verdict.
2. **Student-Side (`statics/testlab/testcases/`):** Contains only the *public* test cases. Students use this subset to verify their code locally before submitting.

Structure:
```
testcases/
└── Q1/
    ├── input/
    │   ├── input00.txt
    │   └── input01.txt
    └── output/
        ├── output00.txt
        └── output01.txt
```

## 5. Preparing the Student Starter Kit
Students download a zip file to start their lab. Prepare this inside the `statics/` folder.
1. Create a directory named after your lab (e.g., `statics/testlab/`).
2. Add the lab manual (`Problem-Statement.pdf`).
3. Add the execution scripts: `grade.sh`, `check.sh`, `submit.sh`.
4. Create a dummy starter code folder (e.g., `CS25B0XX/Q1.c`).
5. Create a subset of public test cases in `testcases/` (so students can test locally without seeing hidden edge cases).
6. Create the hidden configuration directory `.ig_course/` and copy the `config.json` inside it.
7. Zip the directory:
```bash
cd statics
zip -r testlab.zip testlab
```

## 6. Distributing the CLI Tool
1. Edit `clients/setup.sh`. Update the `COURSE_ID` and `DEFAULT_SERVER_URL` at the top of the file.
2. The `setup.sh` script resides on the server itself. To distribute it, you can provide students with a command like `curl http://<server-ip>:<port>/clients/setup.sh | bash`. This command can be shared via class announcements or hosted directly on the course webpage.

## 7. Starting the System
Start the Celery worker to handle evaluations asynchronously:
```bash
celery -A task.capp worker --loglevel=info
```
Start the FastAPI server:
```bash
python main.py
```
