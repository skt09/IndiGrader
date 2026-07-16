# Technical Specifications

## Core Stack
- **Web Framework**: FastAPI (Python 3.9+)
- **Asynchronous Task Queue**: Celery
- **Message Broker**: Redis
- **Containerization/Sandboxing**: Firejail (Linux-only)
- **Client Tooling**: Bash, curl, jq

## Code Evaluation Constraints
The execution environment enforces configuration-defined resource constraints to maintain server stability.
- **I/O Limitations**: The grading engine processes file-based inputs and command-line arguments. By default, **evaluation compares `stdout` streams only**. Evaluation of generated file outputs requires a custom `evaluator.sh` script.
- **Sandboxing**: Server-side execution is isolated via Firejail. Network access is disabled within the sandbox, and compute resources are limited per the lab configuration.
- **Supported Languages**:
  - C (compiled with `gcc -lm`)
  - C++ (compiled with `g++`)
  - Python 3 (interpreted via `python3`)
  - AWK (interpreted via `awk -f`)
  
  *Note: A single lab instance supports concurrent evaluation of multiple questions and programming languages. Language identification is based on the submitted file extension.*

## System Limitations
- **OS Dependency**: Server deployment requires a Linux environment due to the `firejail` dependency.
- **State Storage**: The system utilizes local file system storage (structured directories, `csv`, and `txt` logs) for managing submissions and state. External relational databases are not utilized in the current architecture.

## Author & Generation Statement
This project was authored and is maintained by **Sanket Tarafder**. 
The documentation for this repository was generated using the **Gemini 3.1 Pro (High)** LLM model and has been manually reviewed and verified.
