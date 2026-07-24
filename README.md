# IndiGrader

IndiGrader is an autograding platform designed for closed-network university programming labs, focusing on isolated execution and secure network configuration.

> [!IMPORTANT]
> **Evaluation Boundary:** The grading engine supports `stdin`, command-line arguments, and file-based inputs. However, default evaluations are restricted to comparing `stdout`. Evaluating file outputs requires a custom evaluator script (refer to the Templates section).

## Documentation

Comprehensive documentation is available in the `docs/` directory:
- [Architecture](docs/architecture.md)
- [Technical Specifications](docs/tech_specs.md)
- [Setup Guide](docs/setup_guide.md)
- [Student Workflow](docs/student_workflow.md)
- [Post-Lab & Admin Guide](docs/post_lab_guide.md)

## Templates

IndiGrader utilizes a template-based architecture to support different assignment structures:

- **[Out-of-the-Box Template](templates/out_of_the_box/README.md):** The standard environment for evaluating single-file submissions (C, C++, Python, AWK) and multi-file Makefile projects.
- **[Custom Evaluator Template](templates/custom_evaluator/README.md):** Boilerplate for implementing custom evaluation logic (e.g., partial marking, tolerance thresholds, or format parsing).

## Design Principles

IndiGrader's architecture is guided by the following principles:

- **Isolated Execution:** Grading scripts execute within Firejail sandboxes. This prevents untrusted code from accessing the host network or unauthorized files, ensuring the stability and security of the server environment.
- **Offline Deployment:** Designed for closed networks, the platform operates independently of external services. It relies on local state management and static assets to minimize dependencies and external points of failure.
- **Asynchronous Grading:** To handle burst traffic (e.g., hundreds of concurrent submissions at a lab deadline), the system decouples the web server from the grading engine using a Celery task queue and a Redis broker.
- **CLI-Centric Workflow:** The student interface is provided via a command-line tool (`ig`) rather than a web GUI. This design encourages familiarity with terminal environments and integrates directly into the standard development workflow.

## Capabilities

### Execution Engine
- **Decoupled Evaluation:** A unified evaluation script (`grade.sh`) is utilized for both local student testing and server-side grading, ensuring parity between local results and server verdicts.
- **Input Handling:** The engine detects and processes test cases involving standard input streams, command-line arguments, and auxiliary files.
- **Language Support:** Supports concurrent evaluation of multiple programming languages (C, C++, Python, AWK) within a single lab instance, identifying the target language via file extensions.

### Security Configurations
- **Subnet Binding:** Implements IP binding middleware to restrict access. Initial connections bind a student's roll number to a specific IP address for the duration of the session.
- **Migration Auditing:** Provides a mechanism for machine migration during a lab session, logging rebind events for administrative review.
- **Path Isolation:** Submission histories are indexed numerically, avoiding direct file path transmission and preventing path-traversal vulnerabilities.

### System Administration
- **Global Resource Injection:** Administrators can configure shared static resources (e.g., header files, databases) that are automatically mounted into all evaluation sandboxes.
- **Data Packaging:** Submissions involving multiple files or directories are compressed automatically for transmission.
- **Static Leaderboard:** Generates an offline, static HTML leaderboard reflecting the current grading state without requiring a secondary web framework.


## Acknowledgments & Adoptions

IndiGrader has been utilized across multiple courses at IIT Madras:

- **CS6150 Advanced Programming (Jul-Nov 2025):** The core engine was originally developed for this course. Instructors [Meghana Nasre](https://cse.iitm.ac.in/~meghana/) and [Anantha Padmanabha](https://padmanabha-anantha.github.io/website/) supported its use as the primary evaluation tool in post-midsem labs. Thanks to the CS6150 TA team, specifically [Raj Kumar](https://www.linkedin.com/in/rajkumarseelam/), for proposing the IP Binding mechanism.
- **CS2810 Object Oriented Algorithms, Implementation and Analysis Lab (Jan-May 2026):** Adopted for use in a portion of the course curriculum.
- **CS1234 Small-Scale Application Development (Jan-May 2026):** The platform underwent revisions guided by course instructor [Rupesh Nasre](https://cse.iitm.ac.in/~rupesh/). Feedback from CS1234 students (CSE BTech25 batch) contributed to current feature refinement.
- **CSE DCF Staff (IIT Madras):** Thanks to the CSE Department Computing Facility (DCF) Staff for their assistance with system administration and environment configuration.

## License

This project is licensed under the [MIT License](LICENSE).

## Feedback & Support

For suggestions, feature requests, or issue reporting, contact `cs24s018 [at] cse [dot] iitm [dot] ac [dot] in` or open an issue in the repository.

## Author & Generation Statement

This project was authored and is maintained by **Sanket Tarafder**.
The documentation for this repository was generated using the **Gemini 3.1 Pro (High)** LLM model and has been manually reviewed and verified.
