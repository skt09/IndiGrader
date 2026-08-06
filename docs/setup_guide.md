# IndiGrader Lab Setup Guide

This guide explains how to properly scaffold and deploy an IndiGrader lab environment using the `builder.py` configuration script. 

> [!IMPORTANT]
> **Always pull the latest changes** (`git pull`) from the repository before building a new lab to ensure you have the latest features and bug fixes.

## 1. Prerequisites

**For the Lab Creator's Machine:**
- Python 3 to run the builder script. (No external pip dependencies required).

**For the Lab Server:**
Ensure the machine where the lab will be hosted has the following installed:
- Python 3.9+ (3.12+ recommended)
- Redis Server (`sudo apt install redis-server`)
- Firejail (`sudo apt install firejail`)
- jq (`sudo apt install jq`)

It is highly recommended to create a Python virtual environment on the **Lab Server's** home directory (not in the lab folder) to avoid conflicts. (Note: This setup is only required on the first day if not set up earlier):
```bash
python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install -r requirements.txt
```

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
   *Note: If a program takes a file as a command-line argument (e.g., `./a.out filename.txt`), you must use this mode. Place `filename.txt` in the directory, and create an `args.txt` containing the text `filename.txt`.*
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

## 3. Running the Configuration Script
Run the script from the root of the IndiGrader repository:
```bash
python3 builder.py
```
The script will prompt for:
- Course ID and Lab Name
- Lab Server IP and Lab Server Port (default: 8000)
- Allowed Subnet(s) (prefix matching the lab's local network, e.g., `10.21.225.` or `192.168.1.`)
- Date, Start Date/Time, and Durations
- Testcase paths and memory/timeout limits for each individual question.

> [!TIP]
> **Global Static Files Configuration**
> The script prompts for an optional global `static/` directory for a question. If provided with a directory containing a trusted `main.c` and a `Makefile`, the server will overwrite the student's `main.c` with this trusted version prior to compilation. This restricts the evaluation to specific source files implemented by the student.
>
> **Important Note:** All static files for a given question must reside within a single directory, as only one path can be provided during configuration. During evaluation, the contents of this directory are copied directly into the root of the sandbox environment.

> [!TIP]
> **Makefile Projects**
> The script supports `Makefile` execution. Input `y` when prompted if a question uses a Makefile, and provide a directory path rather than a file path for the starter code. The necessary structure will be scaffolded automatically.

## 4. Deploying to the Server
Once `builder.py` completes, it generates a `packageIG_<LabName>.zip` archive and a `packageIG_<LabName>` directory at the root of the repository. 

**The Generated Server Structure (`packageIG_L8/`)**:
```text
packageIG_L8/
├── config.json                 # Auto-generated lab configuration (includes port & queue_name)
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
1. Runs strict pre-flight checks to validate `config.json`, verify starter `.zip` exists, and check that `celery` and `fastapi` are present in your active Python environment.
2. Starts the Redis broker on port 6379 (if not already running).
3. Starts Celery grading workers with 12 concurrency, bound to the lab's isolated queue (`ig_<course_id>_<lab_name>`).
4. Starts the FastAPI server bound to the configured course port.
5. Verifies both background processes stay alive after startup (displaying crash logs if startup fails).

## 6. Distributing the Lab to Students
Your students can fetch the starter kit directly from the server.
1. Provide students with the command `curl http://<server-ip>:<port>/clients/setup.sh | bash`.
2. This script retrieves the `ig` command-line tool, downloads the lab package, and registers the workstation's IP address on the server.

## 7. Last-Minute Config Changes (During the Lab)
Because performance is critical during peak lab hours, FastAPI loads `config.json` into RAM once at startup rather than reading from disk on every single student request. 

If you need to change the lab time, duration, or memory limits on the fly while the lab is running:
1. Edit the `config.json` file directly on the server (e.g., `nano config.json`).
2. Restart **just** this lab's FastAPI server using its specific port:
   ```bash
   PORT=$(jq -r '.port // 8000' config.json)
   pkill -f "port $PORT" && fastapi run main.py --port "$PORT" > logs/fastapi.log 2>&1 &
   ```
*(Note: Clients that have previously downloaded the starter kit will retain the prior deadline locally, but the server maintains the authoritative state and will evaluate late submissions according to the updated configuration).*

## 8. Graceful Shutdown (`stop.sh`)
When the lab session concludes, avoid terminating the FastAPI server or Celery worker abruptly (e.g., via `Ctrl+C`). Abrupt termination may result in the loss of queued submissions.

Instead, execute the shutdown script:
```bash
./stop.sh
```
**Functionality of `stop.sh`:**
1. Terminates **only** this lab's FastAPI application (via `logs/fastapi.pid` or port) to prevent new submissions.
2. Continually monitors this lab's isolated Redis queue (`ig_<course_id>_<lab_name>`), displaying remaining length on your terminal.
3. Waits until the queue hits `0` (meaning all students for this lab have been graded).
4. Safely sends a `SIGTERM` to this lab's Celery worker (`logs/celery.pid`), leaving other running course labs untouched.

Once `stop.sh` says "Shutdown Complete!", it is safe to zip the folder and take it back to your local machine for post-lab processing (detailed in `post_lab_guide.md`).
