# IndiGrader

IndiGrader is a secure, zero-trust autograding platform designed specifically for closed-network university programming labs. 

> [!IMPORTANT]
> **Limitation:** The grading engine supports complex file inputs, `stdin`, and command line arguments natively, but grading evaluations are strictly restricted to `stdout` comparisons. Hybrid file outputs are not natively supported and require a custom evaluator script.

## Documentation

Comprehensive documentation can be found in the `docs/` directory:
- [Technical Specifications](docs/tech_specs.md)
- [Architecture](docs/architecture.md)
- [Setup Guide](docs/setup_guide.md)
- [Student Workflow](docs/student_workflow.md)

## Acknowledgments & Adoptions

IndiGrader has been successfully utilized and refined across multiple courses at IIT Madras:

*   **CS6150 Advanced Programming (Jul-Nov 2025):** The core engine was originally built for this course. With the encouragement of instructors [Meghana Nasre](https://cse.iitm.ac.in/~meghana/) and [Anantha Padmanabha](https://padmanabha-anantha.github.io/website/), it served as the primary tool substituting HackerRank in post-midsem labs. I also extend my gratitude to the CS6150 TA team, and specifically [Raj Kumar](https://www.linkedin.com/in/rajkumarseelam/) for proposing the foundational idea for the IP Binding security measure.
*   **CS2810 Object Oriented Algorithms, Implementation and Analysis Lab (Jan-May 2026):** Adopted for use in a portion of the course curriculum.
*   **CS1234 Small-Scale Application Development (Jan-May 2026):** The platform underwent numerous revisions and significant enhancements guided by course instructor [Rupesh Nasre](https://cse.iitm.ac.in/~rupesh/). I also extend my gratitude to the CS1234 students (CSE BTech25 batch), whose valuable feedback directly shaped many of the current features.
*   **CSE DCF Staff (IIT Madras):** Special thanks to the CSE Department Computing Facility (DCF) Staff. As the system administrators, their continuous help, support, and permission to configure dependencies on the lab systems were crucial to running the platform.

## Features

IndiGrader is built with three core philosophies in mind:

### Security-Related Features
- **Zero-Trust Architecture:** Grading scripts run in completely isolated environments.
- **Strict IP Binding:** Enforces subnet restrictions to block unauthorized VPN or external connections.
- **Rebind Auditing:** Allows secure machine migration mid-lab while quietly logging all rebind attempts for instructor audit.
- **Path-Traversal Immunity:** Submissions are indexed securely, completely preventing malicious file path requests during history retrieval.

### Student-Focused Features
- **Smart CLI (`ig`):** Intuitive commands (`ig check`, `ig submit`) replacing complex and repetitive bash scripts.
- **Interactive Terminal History:** Students can instantly view and download their past submissions directly in the terminal via `ig history`.
- **Automatic Multi-File Compression:** Projects are automatically `.tar.gz` compressed upon submission, allowing seamless multi-file workflows.
- **Offline Leaderboard:** A premium, zero-dependency dark-mode leaderboard that updates dynamically without external dependencies.

### Engine & Minute Features
- **Hybrid Input System:** The engine dynamically detects testcase structures, natively supporting `stdin` streams, space-separated Command Line Arguments (`args.txt`), and complex directory-based inputs requiring external file I/O operations without manual configuration.
- **Global Static Injection:** Magically injects shared files (like common databases) into all sandboxes automatically, drastically reducing repository redundancy.
- **Decoupled Grading:** A unified `grade.sh` engine used both locally (for public test cases) and server-side (for hidden test cases) to ensure evaluation parity.
- **Asynchronous Task Queues:** Powered by Celery and Redis to handle hundreds of concurrent submissions instantly.
- **Regex Auto-Detection:** Built-in regex engine automatically extracts student Roll Numbers from directory structures, minimizing manual configuration errors.
- **Multi-Question & Multi-Language Support:** A single lab environment natively supports multiple questions (e.g., Q1, Q2) and multiple programming languages (C, C++, Python, AWK) simultaneously, dynamically detecting the language based on the file extension.

## Active Development & Upcoming Features

The following enhancements are in the pipeline for future releases:
- **Student Makefile Support:** Support for complex multi-file project submissions that rely on a custom `Makefile` for compilation.
- **Custom Grading Logic:** A raw bash template allowing instructors to safely interface their own custom evaluation scripts for advanced scenarios (e.g., partial marking, hybrid file outputs, or connected questions where Q1's output is Q2's input).
- **Comprehensive Sample Labs:** A `samples/` directory providing out-of-the-box examples for every type of configuration.

## License
This project is licensed under the [MIT License](LICENSE).

## Feedback & Support
If you have any suggestions, feature requests, or encounter any issues, please feel free to reach out via email at `cs24s018 [at] cse [dot] iitm [dot] ac [dot] in` or open an issue in the repository.

## Author & Generation Statement
This project was authored and is maintained by **Sanket Tarafder**.
The documentation for this repository was generated using the **Gemini 3.1 Pro (High)** LLM model and has been manually reviewed and verified.
