# Architecture

IndiGrader utilizes a decentralized client-server architecture designed specifically for closed-network university labs. It optimizes for zero-trust security, strict subnet enforcement, and offline grading capabilities.

## System Components

### 1. The FastAPI Server
The core application server (`main.py`) acts as the gatekeeper and orchestrator. It exposes RESTful endpoints for:
- Fetching starter kits (`/starter/{roll}`)
- Submitting solutions (`/submit/{qno}`)
- Checking task status and downloading history
- Viewing the live leaderboard (`/leaderboard`)

### 2. Zero-Trust IP Middleware
To prevent impersonation, the server utilizes a strict IP-binding middleware.
- When a student fetches a starter kit for the first time, their IP is permanently bound to their roll number for the duration of the lab.
- Any subsequent submission attempts for that roll number from a different IP address are immediately rejected, and the violation is logged in `violations.csv`.

### 3. Asynchronous Grading Pipeline (Celery + Redis)
During peak lab hours, hundreds of students may submit simultaneously.
- Submissions are accepted instantly and pushed to a Redis broker.
- A Celery worker pool (`task.py`) consumes these tasks in the background.
- The worker executes the grading engine within a Firejail sandbox.
- Results are logged into the file system, and the student's terminal polls the server for completion.

### 4. The Unified Grading Engine
Both the server and the student client rely on a single, unified grading script (`grade.sh`).
- On the server, `task.py` executes `grade.sh --sandbox` against the hidden private test cases.
- On the client, `check.sh` executes `grade.sh` (without sandboxing) against the local public test cases.
- This guarantees absolute parity between local test results and server-side evaluation.

### 5. Smart CLI Client (`ig`)
Students interact with the system entirely through the terminal. The `ig` script acts as a smart wrapper that automatically:
- Resolves the correct `SERVER_URL` via hidden configuration tracking.
- Determines the active question based on directory traversal.
- Packages and transmits source files seamlessly.
