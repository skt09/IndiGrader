# Architecture

IndiGrader utilizes a client-server architecture optimized for closed-network university labs. The design prioritizes isolated code execution, network-level access control, and offline grading capabilities.

## System Components

### 1. Application Server (FastAPI)
The core server (`main.py`) manages request orchestration and state. It exposes RESTful endpoints for:
- Fetching starter kits (`/starter/{roll}`)
- Submitting solutions (`/submit/{qno}`)
- Polling task status and retrieving submission history
- Serving the static leaderboard (`/leaderboard`)

### 2. IP-Binding Middleware
To mitigate impersonation, the server implements an IP-binding middleware.
- Upon the initial fetch of a starter kit, a student's IP address is bound to their roll number for the duration of the session.
- Subsequent requests for that roll number from differing IP addresses are rejected, and these events are logged in `violations.csv`.

### 3. Asynchronous Grading Pipeline (Celery + Redis)
To manage high concurrency during lab sessions:
- Submissions are enqueued to a Redis message broker.
- A Celery worker pool (`task.py`) processes these tasks asynchronously.
- The worker executes the grading engine within a Firejail sandbox.
- Results are written to the local file system, while the client periodically polls the server for task completion.

### 4. Unified Grading Engine
Both the server and the client utilize the same underlying evaluation script (`grade.sh`).
- Server-side execution (`task.py`) runs `grade.sh --sandbox` against private test cases.
- Client-side execution (`check.sh`) runs `grade.sh` (without sandboxing constraints) against public test cases.
- This unified approach ensures behavioral consistency between local testing and server-side grading.

### 5. CLI Client (`ig`)
The primary interface for students is a terminal-based CLI (`ig`). It provides automation for:
- Resolving the configured `SERVER_URL`.
- Identifying the active question via directory context.
- Packaging and transmitting source files to the server.

