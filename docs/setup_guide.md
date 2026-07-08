# IndiGrader Lab Setup Guide

This guide explains how to properly scaffold and deploy an IndiGrader lab environment using the automated `builder.py` wizard. 

## 1. Prerequisites
Ensure the server machine has the following installed:
- Python 3.9+
- Redis Server (`sudo apt install redis-server`)
- Firejail (`sudo apt install firejail`)
- jq (`sudo apt install jq`)

## 2. Preparing Your Raw Materials
Before running the builder, you must prepare the raw files for your lab locally on your computer.

1. **Testcases**: Separate your testcases into a `public` folder (for the students to test locally) and a `private` folder (for the server to grade). Inside these folders, you **must** organize your files into `input/` and `output/` directories. 

   Depending on your lab's requirements, structure the contents using one of the three input modes:

   **A. Stdin-Only Mode (Default)**
   For standard input/output programs.
   ```text
   public/
   ├── input/
   │   └── input01.txt
   └── output/
       └── output01.txt
   ```
   
   **B. Arg-Only Mode**
   For programs that only read command-line arguments.
   ```text
   public/
   ├── input/
   │   └── args01.txt
   └── output/
       └── output01.txt
   ```
   
   **C. Hybrid/Directory Mode (File IO & CLA)**
   For programs that need external data files, arguments, and/or stdin simultaneously.
   ```text
   public/
   ├── input/
   │   └── input01/          <-- Must be a directory
   │       ├── args.txt      (optional command-line arguments)
   │       ├── stdin.txt     (optional standard input)
   │       └── data.csv      (any extra files the student code needs to read)
   └── output/
       └── output01.txt      <-- Flat file for the expected output
   ```
2. **Student Lists**: Keep a `students.txt` containing all roll numbers (e.g., `CS25B001, John Doe`).
3. **PwD List**: Keep a `pwd_students.txt` containing the roll numbers of PwD students who receive extra time.
4. **Starter Code**: Prepare the `starter.c` file that students will build upon.
5. **Problem Statement**: Prepare the global `prob_statement.pdf`.

**Example Raw Material Structure:**
```text
my_raw_lab/
├── prob_statement.pdf
├── students.txt
├── pwd_students.txt
├── starter.c
└── testcases_Q1/
    ├── public/
    │   ├── input/
    │   │   └── input01.txt
    │   └── output/
    │       └── output01.txt
    └── private/
        ├── input/
        │   └── input02.txt
        └── output/
            └── output02.txt
```

## 3. Running the Interactive Builder
Run the automated wizard from the root of the IndiGrader repository:
```bash
python3 builder.py
```
The wizard will securely ask you for:
- Course ID, Lab Name, IP configurations
- Start Date/Time and Durations
- Testcase paths and memory/timeout limits for each individual question.

### Clever Tips & Tricks for the Builder
> [!TIP]
> **LeetCode-Style Assignments**
> The wizard asks for an optional **global `static/` folder** for a question. If you provide one containing a trusted `main.c` and a `Makefile`, the server will aggressively overwrite the student's `main.c` with your trusted version before compiling. This allows you to force students to only implement a specific `solution.c` without being able to tamper with the test framework!

> [!TIP]
> **Makefile Projects**
> The wizard natively supports `Makefile` execution. Simply type `y` when asked if a question uses a Makefile, and provide a folder path instead of a file path for the starter code. The wizard will scaffold the appropriate structure.

## 4. Deploying to the Server
Once `builder.py` finishes, it will generate a `packageIG_<LabName>.zip` file and a `packageIG_<LabName>` folder at the root of the repository. 

**The Generated Server Structure (`packageIG_L8/`)**:
```text
packageIG_L8/
├── config.json                 # Auto-generated lab configuration
├── start.sh                    # Server boot script
├── stop.sh                     # Graceful shutdown script
├── students.txt                
├── pwd_students.txt            
├── .admin/                     # Post-lab grading and sorting scripts
├── statics/
│   ├── L8.zip                  # The Student Starter Kit (Fetched via ig)
│   └── L8/                     # Raw unzipped student starter files
└── testcases/
    └── Q1/
        ├── input/              # ONLY Private inputs
        └── output/             # ONLY Private outputs
```

1. Transfer `packageIG_<LabName>.zip` to the lab server.
2. Unzip it.
3. Start the lab environment!

## 5. Starting the Server
Inside the extracted folder on the server, you will find `start.sh`. Run it:
```bash
chmod +x start.sh
./start.sh
```

**What `start.sh` does:**
1. Runs strict pre-flight checks to validate your `config.json` and ensure the student `statics/` `.zip` was correctly built.
2. Starts the Redis broker.
3. Starts the Celery grading workers in the background.
4. Starts the FastAPI server to accept submissions.

## 6. Distributing the Lab to Students
Your students can fetch the starter kit directly from the server.
1. Provide students with the command `curl http://<server-ip>:<port>/clients/setup.sh | bash`.
2. They will automatically receive the `ig` command-line tool, fetch the lab, and be locked to their workstation's IP!

## 7. Last-Minute Config Changes (During the Lab)
Because performance is critical during peak lab hours, FastAPI loads `config.json` into RAM once at startup rather than reading from disk on every single student request. 

If you need to change the lab time, duration, or memory limits on the fly while the lab is running:
1. Edit the `config.json` file directly on the server (e.g., `nano config.json`).
2. Restart **just** the FastAPI server using this simple one-liner to force it to reload the file into RAM without disrupting the Celery grading queue:
   ```bash
   pkill -f "fastapi run main.py" && fastapi run main.py > logs/fastapi.log 2>&1 &
   ```
*(Note: Students who already downloaded the starter kit will still see the old deadline locally in their terminals, but the server is the ultimate source of truth and will correctly accept their late submissions!)*

## 8. Graceful Shutdown (`stop.sh`)
When the lab is over, **never** hit `Ctrl+C` on the FastAPI server or Celery worker! If you abruptly kill the processes, submissions waiting in the Redis queue will be permanently lost.

Instead, run:
```bash
./stop.sh
```
**What `stop.sh` does:**
1. Instantly stops FastAPI so no new submissions can enter.
2. Continually monitors the Redis queue (displaying the remaining length on your terminal).
3. Waits until the queue hits `0` (meaning all students have been graded).
4. Safely sends a `SIGTERM` to the Celery workers to let them wrap up.

Once `stop.sh` says "Shutdown Complete!", it is safe to zip the folder and take it back to your local machine for post-lab processing (detailed in `post_lab_guide.md`).
