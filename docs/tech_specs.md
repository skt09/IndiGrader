# Technical Specifications

## Core Stack
- **Web Framework**: FastAPI (Python 3.9+)
- **Asynchronous Task Queue**: Celery
- **Message Broker**: Redis
- **Containerization/Sandboxing**: Firejail (Linux-only)
- **Client Tooling**: Bash, curl, jq

## Code Evaluation Constraints
The execution environment enforces strict constraints to ensure server stability and security.
- **I/O Limitations**: The grading engine natively handles complex file-based inputs and command line arguments via its Hybrid Input system. However, **evaluation is strictly restricted to comparing `stdout`**. Generated file outputs are not evaluated automatically unless the instructor provides a custom `evaluator.sh` script.
- **Sandboxing**: Execution is heavily restricted using Firejail when running on the server. Network access is disabled, and process resources are capped according to the configuration.
- **Supported Languages**:
  - C (compiled with `gcc -lm`)
  - C++ (compiled with `g++`)
  - Python 3 (interpreted via `python3`)
  - AWK (interpreted via `awk -f`)
  
  *Note: A single lab can support multiple questions and multiple languages simultaneously. The engine dynamically detects the language based on the submitted file extension.*

## System Limitations
- **OS Dependency**: Requires a Linux environment on the server side due to the reliance on `firejail` for sandboxing.
- **State Storage**: The system relies on local file system storage for submissions, late submissions, and grades. It does not currently use an external relational database, relying instead on structured directories and text logs (`csv` and `txt`).

## Author & Generation Statement
This project was authored and is maintained by **Sanket Tarafder**. 
The documentation for this repository was generated using the **Gemini 3.1 Pro (High)** LLM model and has been manually reviewed and verified.
