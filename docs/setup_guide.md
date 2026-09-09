# IndiGrader Submission-Only Setup Guide

This guide explains how to properly scaffold and deploy an IndiGrader lab environment using the `builder.py` configuration script on this submission-only branch.

> [!IMPORTANT]
> **This branch is strictly for submission-only labs.** Automated grading is completely bypassed.

## 1. Prerequisites

**For the Lab Creator's Machine:**
- Python 3 to run the builder script. (No external pip dependencies required).

**For the Lab Server:**
Ensure the machine where the lab will be hosted has the following installed:
- Python 3.9+ (3.12+ recommended)
- Redis Server (`sudo apt install redis-server`)
- jq (`sudo apt install jq`)

*(Note: Firejail is not required for this submission-only setup since no external code is executed).*

It is highly recommended to create a Python virtual environment on the **Lab Server's** home directory:
```bash
python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install -r requirements.txt
```

## 2. Preparing Your Raw Materials
Before running the builder, you must prepare the raw files for your lab locally on your computer.

1. **Starter Folder**: A folder containing the starter code and notebook (e.g., `Lab-2/`).
2. **Lectures Folder**: A folder containing lecture material.
3. **Previous Submissions Zip**: A zip file of previous submissions for context.
4. **Setup Script**: An initialization script (`set-up-script`).
5. **Student Lists**: Keep a `students.txt` containing all roll numbers (e.g., `CS25B001, John Doe`).
6. **PwD List**: Keep a `pwd_students.txt` containing the roll numbers of PwD students who receive extra time.

## 3. Running the Configuration Script
Run the script from the root of the IndiGrader repository:
```bash
python3 builder.py
```
The script will prompt for:
- Course ID, Lab Name, Server IP configurations
- Allowed Subnet: Provide a prefix matching the lab's local network (e.g., `10.21.225.` or `192.168.1.`) to restrict student access.
- Start Date/Time and Durations
- Paths to your Starter Folder, Lectures Folder, Submissions Zip, and Setup Script.

## 4. Deploying to the Server
Once `builder.py` completes, it generates a `packageIG_<LabName>.zip` archive and a `packageIG_<LabName>` directory at the root of the repository in the `Labs/` folder.

**The Generated Server Structure (`packageIG_L8/`)**:
```text
packageIG_L8/
├── config.json                 # Auto-generated lab configuration
├── start.sh                    # Server boot script
├── stop.sh                     # Graceful shutdown script
├── students.txt                
├── pwd_students.txt            
├── statics/
│   ├── L8.zip                  # The Student Starter Kit (Fetched via ig)
│   └── L8/                     # Raw unzipped student starter files
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
1. Runs strict pre-flight checks.
2. Starts the Redis broker.
3. Starts the Celery task workers in the background (used only for fast saving of files).
4. Starts the FastAPI server to accept submissions.

## 6. Distributing the Lab to Students
Your students can fetch the starter kit directly from the server.
1. Provide students with the command `curl http://<server-ip>:<port>/clients/setup.sh | bash`.
2. This script retrieves the `ig` command-line tool, downloads the lab package, and registers the workstation's IP address on the server.

## 7. Graceful Shutdown (`stop.sh`)
When the lab session concludes, execute the shutdown script:
```bash
./stop.sh
```
This safely stops the server and ensures all pending submissions are saved.
