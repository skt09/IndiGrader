import os
import sys
import argparse
import json
import shutil
import subprocess
import tempfile
import time
import difflib
import resource

import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TestResult:
	test_name: str
	status: str
	execution_time: float = 0.0
	exit_code: Optional[int] = None
	message: str = ""
	stdout: str = ""
	stderr: str = ""

@dataclass
class GradeResult:
	passed: int
	total: int
	status: str = "COMPLETED"
	tests: List[TestResult] = field(default_factory=list)
	message: str = ""

	@property
	def score(self):
		return f"{self.passed}/{self.total}"

	def to_dict(self):
		return {
			"status": self.status,
			"passed": self.passed,
			"total": self.total,
			"score": self.score,
			"message": self.message,
			"tests": [
				{
					"test_name": test.test_name,
					"status": test.status,
					"execution_time": test.execution_time,
					"exit_code": test.exit_code,
					"message": test.message,
					"stdout": test.stdout,
					"stderr": test.stderr
				}
				for test in self.tests
			]
		}


# Standardized Flags
# CFLAGS="-Wall"
# CXXFLAGS="-Wall"
# LDFLAGS="-lm -lpthread"
CFLAGS = ["-Wall"]
CXXFLAGS = ["-Wall"]
LDFLAGS = ["-lm", "-lpthread"]


# SUBMISSION=""
# QUESTION=""
# TESTCASES_DIR=""
# SANDBOX=false
# CONFIG_FILE="config.json"
# TARGET_TESTCASE=""
# SAVE_OUTPUT_DIR=""
# Parse arguments
# while [[ "$#" -gt 0 ]]; do
#     case $1 in
#         --submission) SUBMISSION="$2"; shift ;;
#         --question) QUESTION="$2"; shift ;;
#         --testcases_dir) TESTCASES_DIR="$2"; shift ;;
#         --sandbox) SANDBOX=true ;;
#         --config) CONFIG_FILE="$2"; shift ;;
#         -t|--testcase) TARGET_TESTCASE="$2"; shift ;;
#         --save_output_dir) SAVE_OUTPUT_DIR="$2"; shift ;;
#         *) echo "[LOG] Unknown parameter: $1"; exit 1 ;;
#     esac
#     shift
# done
def parse_arguments():
	parser = argparse.ArgumentParser(description="Unified Grader (Python Version)")
	parser.add_argument("--submission", required=True, help="Path to submission file/directory")
	parser.add_argument("--question", required=True, help="Question name/ID")
	parser.add_argument("--testcases_dir", required=True, help="Directory containing testcases")

# if [ -z "$SUBMISSION" ] || [ -z "$QUESTION" ] || [ -z "$TESTCASES_DIR" ]; then
#     echo "[LOG] Missing required arguments: --submission, --question, --testcases_dir"
#     exit 1
# fi

	parser.add_argument("--sandbox", action="store_true", help="Enable sandboxing (uses firejail if available)")
	parser.add_argument("--config", default="config.json", help="Path to configuration file")
	parser.add_argument("-t", "--testcase", default="", help="Target a specific testcase ID")
	parser.add_argument("--save_output_dir", default="", help="Directory to save execution stdout files")
	parser.add_argument("--json", action="store_true", help="Emit structured JSON output")
	return parser.parse_args()


def load_config(config_file, question):

	# if [ ! -f "$CONFIG_FILE" ]; then
	# 	echo "[LOG] Config file not found: $CONFIG_FILE"
	# 	exit 1
	# fi

	# # Load config
	# EVALUATOR=$(jq -r ".\"$QUESTION\".evaluator // empty" "$CONFIG_FILE" 2>/dev/null)
	# TIMEOUT_SEC=$(jq -r ".\"$QUESTION\".timeout // 5" "$CONFIG_FILE" 2>/dev/null)
	# MEM_CAP_MB=$(jq -r ".\"$QUESTION\".memory_cap_mb // 512" "$CONFIG_FILE" 2>/dev/null)
	# MAKEFILE_MODE=$(jq -r ".\"$QUESTION\".makefile // false" "$CONFIG_FILE" 2>/dev/null)
	# EXEC_NAME=$(jq -r ".\"$QUESTION\".executable_name // \"$QUESTION\"" "$CONFIG_FILE" 2>/dev/null)


	if not os.path.isfile(config_file):
		print(f"[LOG] Config file not found: {config_file}")
		sys.exit(1)

	try:
		with open(config_file, "r") as f:
			config = json.load(f)
	except Exception:
		config = {}

	q_config = config.get(question, {})
	evaluator = q_config.get("evaluator", None)
	timeout_sec = q_config.get("timeout", 5)
	memory_cap_mb = q_config.get("memory_cap_mb", 512)
	makefile_mode = q_config.get("makefile", False)
	exec_name = q_config.get("executable_name", question)

	if isinstance(makefile_mode, str):
		makefile_mode = makefile_mode.lower() == "true"

	return evaluator, timeout_sec, memory_cap_mb, makefile_mode, exec_name

def strip_leading_zeros(s):
	return s.lstrip('0') if s else ""


def _normalize_output_lines(lines):
	result = []

	for line in lines:
		# === Flag: -B (ignore blank lines) ===
		# Skip any line that is empty or contains only whitespace
		# line.strip() removes leading/trailing whitespace to detect truly blank lines
		if not line.strip():
			continue

        # === Flag: -w (ignore all whitespace) ===
		# re.sub(r"\s+", "", line) removes EVERY whitespace character
		# (spaces, tabs, newlines, etc.) from the entire line
		# This makes internal whitespace irrelevant for comparison
		# Example: "foo  bar" → "foobar"
		#          "f o o b a r" → "foobar"
		
		# === Flag: -i (ignore case) ===
		# .casefold() converts the string to lowercase
		# This is case-insensitive comparison
		# Example: "FooBar" → "foobar"
		result.append(
			re.sub(r"\s+", "", line).casefold()
		)

	return result


def diff_files(actual_path, expected_path):
	"""OS-independent line-by-line comparison ignoring trailing whitespace and blank lines."""
	# DONE This IS changed for exact grading equivalence.



	try:
		with open(actual_path, 'r', encoding='utf-8', errors='ignore') as f1, \
			 open(expected_path, 'r', encoding='utf-8', errors='ignore') as f2:

			lines1 = _normalize_output_lines(f1)
			lines2 = _normalize_output_lines(f2)

			return lines1 == lines2
	except Exception:
		return False


def print_diff_snippet(actual_path, expected_path):
	"""Fallback cross-platform unified diff snippet generator."""
	try:
		with open(expected_path, 'r', encoding='utf-8', errors='ignore') as f2, \
			 open(actual_path, 'r', encoding='utf-8', errors='ignore') as f1:

			expected_lines = [
				line + "\n"
				for line in _normalize_output_lines(f2)
			]

			actual_lines = [
				line + "\n"
				for line in _normalize_output_lines(f1)
			]

			diff = difflib.unified_diff(
				expected_lines,
				actual_lines,
				fromfile='Expected',
				tofile='Actual',
				n=3
			)

			for i, line in enumerate(diff):
				if i >= 15:
					break
				print(f"[LOG] {line.rstrip()}")
	except Exception as e:
		print(f"[LOG] Could not generate diff: {e}")


def _copy_contents_without_hidden_files(source_dir, destination_dir):
	# === Skip hidden files ===
    # This addresses "Problematic Python copytree() copy hidden files"
    # In shell, the glob pattern * never expands to hidden files
    # We must explicitly exclude them in Python
    # Examples: .git, .gitignore, .env, __pycache__ (starts with .)
	for item in os.listdir(source_dir):
		if item.startswith("."):
			continue

		s = os.path.join(source_dir, item)
		d = os.path.join(destination_dir, item)

		if os.path.isdir(s):
			shutil.copytree(s, d, dirs_exist_ok=True)
		else:
			shutil.copy2(s, d)


def run_standard(
	executable,
	input_item,
	expected_output,
	sandbox_dir,
	test_name,
	ext,
	timeout_sec,
	memory_cap_mb,
	sandbox_flag,
	testcases_dir,
	question,
	quiet=False
):
	expected_output = os.path.abspath(expected_output)
	os.makedirs(sandbox_dir, exist_ok=True)
	actual_output = os.path.join(sandbox_dir, "stdout.txt")
	stderr_output = os.path.join(sandbox_dir, "stderr.txt")


	# DONE Problamatic Python copytree() copy hidden files.

	# Global Static Injection
	# if [ -d "$TESTCASES_DIR/$QUESTION/static" ]; then
	#     cp -r "$TESTCASES_DIR/$QUESTION/static/"* "$sandbox_dir/" 2>/dev/null || true
	# fi
	q_static_dir = os.path.join(testcases_dir, question, "static")
	if os.path.isdir(q_static_dir):
		_copy_contents_without_hidden_files(q_static_dir, sandbox_dir)


	# DONE Problamatic Python copytree() copy hidden files.

	# local stdin_file="/dev/null"
	# local args_file="/dev/null"
	stdin_file = None
	args_file = None

	# if [ -d "$input_item" ]; then
	if os.path.isdir(input_item):
		# Directory Mode (Hybrid)
		# cp -r "$input_item/"* "$sandbox_dir/" 2>/dev/null || true
		# if [ -f "$sandbox_dir/stdin.txt" ]; then
		#     stdin_file="$sandbox_dir/stdin.txt"
		# fi
		# if [ -f "$sandbox_dir/args.txt" ]; then
		#     args_file="$sandbox_dir/args.txt"
		# fi
		_copy_contents_without_hidden_files(input_item, sandbox_dir)

		potential_stdin = os.path.join(sandbox_dir, "stdin.txt")
		if os.path.isfile(potential_stdin):
			stdin_file = potential_stdin

		potential_args = os.path.join(sandbox_dir, "args.txt")
		if os.path.isfile(potential_args):
			args_file = potential_args

	# elif [[ "$input_item" == *args*.txt ]]; then
	#     # Arg-only Mode
	#     if [[ ! "$input_item" == /* ]]; then
	#         args_file="$PWD/$input_item"
	#     else
	#         args_file="$input_item"
	#     fi
	elif "args" in os.path.basename(input_item) and input_item.endswith(".txt"):
		# Arg-only Mode
		args_file = os.path.abspath(input_item)

	# else
	#     # Stdin-only Mode
	#     if [[ ! "$input_item" == /* ]]; then
	#         stdin_file="$PWD/$input_item"
	#     else
	#         stdin_file="$input_item"
	#     fi
	# fi
	else:
		# Stdin-only Mode
		stdin_file = os.path.abspath(input_item)

	# Copy executable/source to sandbox_dir
	# local local_exec=$(basename "$EXECUTABLE")
	# cp -r "$EXECUTABLE" "$sandbox_dir/"
	local_exec = os.path.basename(executable)
	dest_exec = os.path.join(sandbox_dir, local_exec)
	if os.path.isdir(executable):
		shutil.copytree(executable, dest_exec, dirs_exist_ok=True)
	else:
		shutil.copy2(executable, dest_exec)

	# Command array construction
	# local CMD=()
	cmd = []


	# DONE Problamatic If Firejail isn't installed.Python Simply doesn't use Firejail.
	# Requesting sandboxing and silently running unsandboxed is not ideal.

    # TODO Add other sandbox environment to support other OSs 

	# Firejail is Linux specific; skipped on Windows/Mac dynamically
	# if [ "$SANDBOX" = true ]; then
	#     CMD=("firejail" "--quiet" "--noprofile" "--private=.")
	# fi
	if sandbox_flag and os.name == 'posix':
		# === Lookup firejail once and store the result ===
		# shutil.which() returns the full path if found, None if not found
		# Example: "/usr/bin/firejail" or None
		firejail = shutil.which("firejail")

		if firejail:
			# Use the actual path (not a hardcoded string)
			# This handles systems where firejail is in non-standard paths
			cmd += [firejail, "--quiet", "--noprofile", "--private=."]
		else:
			# === Write error to stderr file ===
			# Sandbox was explicitly requested but is not available
			# This is a framework error, not a test failure
			with open(stderr_output, "w") as err_f:
				err_f.write(
					"Execution Framework Error: firejail not found.\n"
				)

			if not quiet:
				print(
					f"[VERDICT] {test_name}: RUNTIME_ERROR (0.000000s)"
				)
				print("[LOG] Execution Framework Error: firejail not found.")

            # === Early return with error status ===
			# Exit code 3: Framework/environment error (not test logic error)
			# Return a TestResult with RUNTIME_ERROR status
			# This prevents the executable from running unsandboxed

			return (
				3,
				TestResult(
					test_name=test_name,
					status="RUNTIME_ERROR",
					execution_time=0.0,
					exit_code=3,
					message="Execution Framework Error: firejail not found.",
					stderr="Execution Framework Error: firejail not found.\n"
				)
			)


	# if [[ "$EXT" == ".py" ]]; then
	#     CMD+=("python3" "./$local_exec")
	# elif [[ "$EXT" == ".awk" ]]; then
	#     CMD+=("awk" "-f" "./$local_exec")
	# else
	#     CMD+=("./$local_exec")
	# fi
	if ext == ".py":
		cmd += ["python3" if os.name != 'nt' else "python", f"./{local_exec}"]
	elif ext == ".awk":
		cmd += ["awk", "-f", f"./{local_exec}"]
	else:
		if os.name == 'nt':
			cmd += [local_exec]
		else:
			cmd += [f"./{local_exec}"]

	# Load args
	# local EXTRA_ARGS=()
	# if [ -f "$args_file" ]; then
	#     EXTRA_ARGS=($(cat "$args_file"))
	# fi
	extra_args = []
	if args_file and os.path.isfile(args_file):
		try:
			with open(args_file, "r") as f:
				extra_args = f.read().split()
		except Exception:
			pass

	full_cmd = cmd + extra_args

	# Run command configuration
	stdin_stream = open(stdin_file, "r") if stdin_file else subprocess.DEVNULL
	stdout_stream = open(actual_output, "w")
	stderr_stream = open(stderr_output, "w")

	orig_cwd = os.getcwd()
	os.chdir(sandbox_dir)

	start_time = time.perf_counter()
	exit_code = 0
	timeout_occurred = False

    # TODO Need Verfication
	# DONE Problamatic The Python implementation should inspect the current limit and
	#                   safely reduce it rather than blindly trying to increase the hard limit.

	# Unix-only memory capping configuration
	def set_limits():
		if os.name == 'posix':
			try:

				limit_bytes = memory_cap_mb * 1024 * 1024

				# === Read the CURRENT limits from the OS ===
                # getrlimit() returns a tuple: (soft_limit, hard_limit)
				# Soft limit: enforced by the OS, can be raised up to the hard limit
				# Hard limit: ceiling; cannot be increased by unprivileged processes
				current_soft, current_hard = resource.getrlimit(resource.RLIMIT_AS)

                # === Handle the unlimited hard limit case ===
				# resource.RLIM_INFINITY is the system constant for "no limit"
				# If hard limit is already unlimited, we can safely set soft to our desired cap
				if current_hard == resource.RLIM_INFINITY:
					new_soft = limit_bytes
				else:
					# We CANNOT exceed the hard limit.
					# Use min() to ensure new_soft <= hard limit
					# Example:
					#   - memory_cap_mb = 256 MB (limit_bytes = 268,435,456 bytes)
					#   - current_hard = 128 MB (134,217,728 bytes)
					#   - new_soft = min(268M, 128M) = 128M ✓
					new_soft = min(limit_bytes, current_hard)

                # === Set the new soft limit, preserve the hard limit ===
				# By passing current_hard unchanged, we never attempt to increase it
				# This respects Unix semantics: only unprivileged process can lower hard limit
				resource.setrlimit(
					resource.RLIMIT_AS,
					(new_soft, current_hard)
				)
			except Exception:
				pass

	try:
		proc = subprocess.run(
			full_cmd,
			stdin=stdin_stream,
			stdout=stdout_stream,
			stderr=stderr_stream,
			timeout=timeout_sec,
			preexec_fn=set_limits if os.name == 'posix' else None
		)
		exit_code = proc.returncode

	# TODO produce TIMEOUT process-tree behavior can differ.
    # `timeout` and Python's `subprocess.run(timeout=...)` do not necessarily kill an entire descendant process tree in exactly the same way. 

	except subprocess.TimeoutExpired:
		timeout_occurred = True
	except Exception as e:
		exit_code = -1
		with open(stderr_output, "a") as err_f:
			err_f.write(f"\nExecution Framework Error: {str(e)}")
	finally:
		if stdin_file:
			stdin_stream.close()
		stdout_stream.close()
		stderr_stream.close()
		os.chdir(orig_cwd)


	# DONE if /usr/bin/time isn't present, the shell leaves the execution time blank.
	# Python always generates a time.

	exec_time = time.perf_counter() - start_time


	# if [ $exit_code -eq 124 ]; then
	#     echo "[VERDICT] $test_name: TIMEOUT (${exec_time}s)"
	#     return 2
	# elif [ $exit_code -ne 0 ]; then
	#     echo "[VERDICT] $test_name: RUNTIME_ERROR (${exec_time}s)"
	#     echo "[LOG] Exit code $exit_code. Stderr:"
	#     cat "$sandbox_dir/stderr.txt" | while read -r line; do echo "[LOG] $line"; done
	#     return 3
	# fi
	if timeout_occurred:
		status = "TIMEOUT"

		if not quiet:
			print(f"[VERDICT] {test_name}: TIMEOUT ({exec_time:.6f}s)")

		return (
			2,
			TestResult(
				test_name=test_name,
				status=status,
				execution_time=exec_time,
				exit_code=124,
				message="Execution timed out."
			)
		)

	elif exit_code != 0:
		stderr_text = ""

		if os.path.isfile(stderr_output):
			with open(stderr_output, "r", errors='ignore') as err_f:
				stderr_text = err_f.read()

		if not quiet:
			print(f"[VERDICT] {test_name}: RUNTIME_ERROR ({exec_time:.6f}s)")
			print(f"[LOG] Exit code {exit_code}. Stderr:")

			for line in stderr_text.splitlines():
				print(f"[LOG] {line}")

		return (
			3,
			TestResult(
				test_name=test_name,
				status="RUNTIME_ERROR",
				execution_time=exec_time,
				exit_code=exit_code,
				message=f"Exit code {exit_code}",
				stderr=stderr_text
			)
		)

	# Diffing logic
	# if diff $DIFF_FLAGS "$actual_output" "$expected_output" > /dev/null 2>&1; then
	#     echo "[VERDICT] $test_name: PASSED (${exec_time}s)"
	#     return 0
	if diff_files(actual_output, expected_output):
		if not quiet:
			print(f"[VERDICT] {test_name}: PASSED ({exec_time:.6f}s)")

		stdout_text = ""
		if os.path.isfile(actual_output):
			with open(actual_output, "r", errors="ignore") as out_f:
				stdout_text = out_f.read()

		return (
			0,
			TestResult(
				test_name=test_name,
				status="PASSED",
				execution_time=exec_time,
				exit_code=0,
				stdout=stdout_text
			)
		)

	# else
	#     echo "[VERDICT] $test_name: WRONG_ANSWER (${exec_time}s)"
	#     echo "[LOG] Diff snippet (Expected vs Actual):"
	#     diff -u --color=always "$expected_output" "$actual_output" | head -n 15 | while read -r line; do echo "[LOG] $line"; done
	#     return 1
	# fi
	else:
		if not quiet:
			print(f"[VERDICT] {test_name}: WRONG_ANSWER ({exec_time:.6f}s)")
			print("[LOG] Diff snippet (Expected vs Actual):")
			print_diff_snippet(actual_output, expected_output)

		stdout_text = ""
		if os.path.isfile(actual_output):
			with open(actual_output, "r", errors="ignore") as out_f:
				stdout_text = out_f.read()

		return (
			1,
			TestResult(
				test_name=test_name,
				status="WRONG_ANSWER",
				execution_time=exec_time,
				exit_code=0,
				message="Output mismatch.",
				stdout=stdout_text
			)
		)

def grade(
	submission,
	question,
	testcases_dir,
	sandbox=False,
	config_file="config.json",
	target_testcase="",
	save_output_dir="",
	quiet=False
):
	evaluator, timeout_sec, memory_cap_mb, makefile_mode, exec_name = load_config(
		config_file,
		question
	)

	# Detect extension
	# FILENAME=$(basename "$SUBMISSION")
	# EXT="${FILENAME##*.}"
	# if [[ "$FILENAME" == "$EXT" ]]; then
	# 	EXT=""
	# else
	# 	EXT=".$EXT"
	# fi

	filename = os.path.basename(submission)
	name_part, ext = os.path.splitext(filename)


	# Compilation step (if not using custom evaluator that handles compilation)
	# Actually, we should compile if it's .c or .cpp
	# EXECUTABLE="$SUBMISSION"
	# BUILD_DIR=$(mktemp -d -t ig_build_XXXXXX)
	# trap 'rm -rf "$BUILD_DIR"' EXIT

	executable = submission
	build_dir = tempfile.mkdtemp(prefix="ig_build_")

	try:
		# if [ "$MAKEFILE_MODE" == "true" ]; then
		if makefile_mode:
			# if [ ! -d "$SUBMISSION" ]; then
			# 	echo "[LOG] Error: Expected a directory for Makefile project, got file: $SUBMISSION"
			# 	echo "[VERDICT] ALL: COMPILATION_ERROR"
			# 	exit 1
			# fi
			if not os.path.isdir(submission):
				message = (
					f"Expected a directory for Makefile project, got file: {submission}"
				)

				if not quiet:
					print(f"[LOG] Error: {message}")
					print("[VERDICT] ALL: COMPILATION_ERROR")

				return GradeResult(
					passed=0,
					total=0,
					status="COMPILATION_ERROR",
					message=message
				)


			# DONE Problamatic Python copytree() copy hidden files.

			# echo "[LOG] Compiling via Makefile in temporary sandbox..."
			# cp -r "$SUBMISSION"/* "$BUILD_DIR/"
			# if [ -d "${TESTCASES_DIR}/static" ]; then
			# 	cp -rf "${TESTCASES_DIR}/static/"* "$BUILD_DIR/" 2>/dev/null
			# fi
			if not quiet:
				print("[LOG] Compiling via Makefile in temporary sandbox...")

			_copy_contents_without_hidden_files(submission, build_dir)

			static_dir = os.path.join(testcases_dir, "static")
			if os.path.isdir(static_dir):
				_copy_contents_without_hidden_files(static_dir, build_dir)

			# if [ -d "${TESTCASES_DIR}/${QUESTION}/static" ]; then
			# 	cp -rf "${TESTCASES_DIR}/${QUESTION}/static/"* "$BUILD_DIR/" 2>/dev/null
			# fi
			q_static_dir = os.path.join(testcases_dir, question, "static")
			if os.path.isdir(q_static_dir):
				_copy_contents_without_hidden_files(q_static_dir, build_dir)

			orig_dir = os.getcwd()
			os.chdir(build_dir)

			compile_log = "compile_log.txt"
			make_cmd = ["make"] if os.name != 'nt' else ["mingw32-make", "make"]

			success = False
			for cmd in make_cmd:
				if shutil.which(cmd):
					with open(compile_log, "w") as log_f:
						res = subprocess.run(
							[cmd],
							stdout=log_f,
							stderr=subprocess.STDOUT
						)
						success = (res.returncode == 0)
					break
			else:
				with open(compile_log, "w") as log_f:
					log_f.write(
						"No 'make' engine tool found on this OS environment."
					)
					success = False

			# if ! make > "compile_log.txt" 2>&1; then
			# 	echo "[COMPILE_LOG] Compilation failed:"
			# 	cat "compile_log.txt" | while read -r line; do echo "[COMPILE_LOG] $line"; done
			# 	echo "[VERDICT] ALL: COMPILATION_ERROR"
			# 	exit 1
			# fi

			if not success:
				compile_output = ""

				if os.path.isfile(compile_log):
					with open(compile_log, "r", errors="ignore") as log_f:
						compile_output = log_f.read()

				os.chdir(orig_dir)

				if not quiet:
					print("[COMPILE_LOG] Compilation failed:")
					for line in compile_output.splitlines():
						print(f"[COMPILE_LOG] {line}")
					print("[VERDICT] ALL: COMPILATION_ERROR")

				return GradeResult(
					passed=0,
					total=0,
					status="COMPILATION_ERROR",
					message=compile_output
				)

			# EXECUTABLE="${BUILD_DIR}/${EXEC_NAME}"
			# cd - >/dev/null

			executable = os.path.join(build_dir, exec_name)
			os.chdir(orig_dir)


		# elif [[ "$EXT" == ".c" ]]; then
		elif ext == ".c":
			# EXECUTABLE="${BUILD_DIR}/exec"
			# echo "[LOG] Compiling C source..."
			executable = os.path.join(
				build_dir,
				"exec" + (".exe" if os.name == 'nt' else "")
			)

			if not quiet:
				print("[LOG] Compiling C source...")

			compile_err = os.path.join(build_dir, "compile_err.txt")

			with open(compile_err, "w") as err_f:
				res = subprocess.run(
					["gcc"] + CFLAGS + [submission] + LDFLAGS + ["-o", executable],
					stderr=err_f
				)

			# if ! gcc $CFLAGS "$SUBMISSION" $LDFLAGS -o "$EXECUTABLE" 2> "${BUILD_DIR}/compile_err.txt"; then
			# 	echo "[COMPILE_LOG] Compilation failed:"
			# 	cat "${BUILD_DIR}/compile_err.txt" | while read -r line; do echo "[COMPILE_LOG] $line"; done
			# 	echo "[VERDICT] ALL: COMPILATION_ERROR"
			# 	exit 1
			# fi
			if res.returncode != 0:
				compile_output = ""

				with open(compile_err, "r", errors="ignore") as err_f:
					compile_output = err_f.read()

				if not quiet:
					print("[COMPILE_LOG] Compilation failed:")
					for line in compile_output.splitlines():
						print(f"[COMPILE_LOG] {line}")
					print("[VERDICT] ALL: COMPILATION_ERROR")

				return GradeResult(
					passed=0,
					total=0,
					status="COMPILATION_ERROR",
					message=compile_output
				)

		# elif [[ "$EXT" == ".cpp" ]]; then
		elif ext == ".cpp":

			# EXECUTABLE="${BUILD_DIR}/exec"
			# echo "[LOG] Compiling C++ source..."
			executable = os.path.join(
				build_dir,
				"exec" + (".exe" if os.name == 'nt' else "")
			)

			if not quiet:
				print("[LOG] Compiling C++ source...")

			compile_err = os.path.join(build_dir, "compile_err.txt")

			with open(compile_err, "w") as err_f:
				res = subprocess.run(
					["g++"] + CXXFLAGS + [submission] + LDFLAGS + ["-o", executable],
					stderr=err_f
				)

			# if ! g++ $CXXFLAGS "$SUBMISSION" $LDFLAGS -o "$EXECUTABLE" 2> "${BUILD_DIR}/compile_err.txt"; then
			# 	echo "[COMPILE_LOG] Compilation failed:"
			# 	cat "${BUILD_DIR}/compile_err.txt" | while read -r line; do echo "[COMPILE_LOG] $line"; done
			# 	echo "[VERDICT] ALL: COMPILATION_ERROR"
			# 	exit 1
			# fi
			if res.returncode != 0:
				compile_output = ""

				with open(compile_err, "r", errors="ignore") as err_f:
					compile_output = err_f.read()

				if not quiet:
					print("[COMPILE_LOG] Compilation failed:")
					for line in compile_output.splitlines():
						print(f"[COMPILE_LOG] {line}")
					print("[VERDICT] ALL: COMPILATION_ERROR")

				return GradeResult(
					passed=0,
					total=0,
					status="COMPILATION_ERROR",
					message=compile_output
				)


		# # Make EXECUTABLE absolute if it's not already
		# if [[ ! "$EXECUTABLE" == /* ]]; then
		# 	EXECUTABLE="$PWD/$EXECUTABLE"
		# fi
		if not os.path.isabs(executable):
			executable = os.path.abspath(executable)


		# Run tests
		# TOTAL=0
		# PASSED=0

		# # Ensure testcases dir exists
		# Q_INPUT_DIR="$TESTCASES_DIR/$QUESTION/input"
		# Q_OUTPUT_DIR="$TESTCASES_DIR/$QUESTION/output"

		# if [ ! -d "$Q_INPUT_DIR" ]; then
		# 	echo "[LOG] No input directory found at $Q_INPUT_DIR"
		# 	exit 1
		# fi

		total_tests = 0
		passed_tests = 0
		test_results = []

		q_input_dir = os.path.join(testcases_dir, question, "input")
		q_output_dir = os.path.join(testcases_dir, question, "output")

		if not os.path.isdir(q_input_dir):
			message = f"No input directory found at {q_input_dir}"

			if not quiet:
				print(f"[LOG] {message}")

			return GradeResult(
				passed=0,
				total=0,
				status="INPUT_DIRECTORY_ERROR",
				message=message
			)


		# Python will attempt to grade Hidden file (eg; .input01) while shell won't.

		input_items = sorted(
			item
			for item in os.listdir(q_input_dir)
			if not item.startswith(".")
		)

		# for input_item in "$Q_INPUT_DIR"/*; do
		# 	[ -e "$input_item" ] || continue
		for item in input_items:

			# DONE This means Python performs only one prefix removal.
			# TODO Can argsinput be a files name if yes need args removal followed by input removal

			# test_case_name=$(basename "$input_item" | sed -e 's/^input//' -e 's/^args//')
			input_item_path = os.path.join(q_input_dir, item)
			test_case_name = item

			if test_case_name.startswith("input"):
				test_case_name = test_case_name[5:]

			if test_case_name.startswith("args"):
				test_case_name = test_case_name[4:]

			# if [[ "$test_case_name" == *.txt ]]; then
			# 	test_case_name="${test_case_name%.txt}"
			# fi
			if test_case_name.endswith(".txt"):
				test_case_name = test_case_name[:-4]

			# # Targeted testcase filter
			# if [ -n "$TARGET_TESTCASE" ]; then
			# 	# Strip leading zeros for a fair numerical comparison (so 4 == 04)
			# 	stripped_target=$(echo "$TARGET_TESTCASE" | sed 's/^0*//')
			# 	stripped_current=$(echo "$test_case_name" | sed 's/^0*//')
			# 	if [ "$stripped_current" != "$stripped_target" ]; then
			# 		continue
			# 	fi
			# fi
			if target_testcase:
				stripped_target = strip_leading_zeros(target_testcase)
				stripped_current = strip_leading_zeros(test_case_name)

				if stripped_current != stripped_target:
					continue


			# TOTAL=$((TOTAL + 1))
			total_tests += 1

			# expected_output="$Q_OUTPUT_DIR/output${test_case_name}"
			expected_output = os.path.join(
				q_output_dir,
				f"output{test_case_name}"
			)

			# # Might be a .txt or a directory
			# if [ ! -e "$expected_output" ] && [ -e "${expected_output}.txt" ]; then
			# 	expected_output="${expected_output}.txt"
			# fi
			if (
				not os.path.exists(expected_output)
				and os.path.exists(expected_output + ".txt")
			):
				expected_output += ".txt"


			# sandbox_dir=$(mktemp -d -t sandbox_XXXXXX)
			sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")

			try:
				# # Evaluate
				# if [ -n "$EVALUATOR" ] && [ "$EVALUATOR" != "null" ]; then
				if evaluator and evaluator != "null":
					

					# Custom Evaluation
					# # Resolve to absolute paths if evaluator assumes it
					# EVAL_SCRIPT="$(cd $(dirname "$CONFIG_FILE") && pwd)/$EVALUATOR"
					# if [ ! -x "$EVAL_SCRIPT" ]; then
					# 	chmod +x "$EVAL_SCRIPT"
					# fi
					eval_script = os.path.abspath(
						os.path.join(
							os.path.dirname(config_file),
							evaluator
						)
					)

                    # TODO Need to implement same for other OSs
					# DONE FOR POSIX Python doesn't chmod. If evaluator exists but isn't executable grader can crash

					if os.path.isfile(eval_script) and os.name == "posix":
						try:
							mode = os.stat(eval_script).st_mode
							os.chmod(eval_script, mode | 0o111)
						except Exception:
							pass

					# Pass EXECUTABLE, input_item, expected_output, sandbox_dir, timeout, sandbox_flag
					# "$EVAL_SCRIPT" "$EXECUTABLE" "$input_item" "$expected_output" "$sandbox_dir" "$TIMEOUT_SEC" "$SANDBOX"
					# exit_code=$?
					run_args = [
						executable,
						input_item_path,
						expected_output,
						sandbox_dir,
						str(timeout_sec),
						str(sandbox).lower()
					]

					if os.name == 'nt' and eval_script.endswith('.sh'):
						eval_cmd = ["bash", eval_script] + run_args
					else:
						eval_cmd = [eval_script] + run_args

					try:
						res = subprocess.run(
							eval_cmd,
							stdout=subprocess.PIPE,
							stderr=subprocess.PIPE,
							text=True
						)

						exit_code = res.returncode
						evaluator_stdout = res.stdout or ""
						evaluator_stderr = res.stderr or ""

					except Exception as e:
						exit_code = 3
						evaluator_stdout = ""
						evaluator_stderr = str(e)

					# exit_code=$?
					# if [ $exit_code -eq 0 ]; then
					# 	echo "[VERDICT] $test_case_name: PASSED"
					# 	PASSED=$((PASSED + 1))
					if exit_code == 0:
						if not quiet:
							print(f"[VERDICT] {test_case_name}: PASSED")

						passed_tests += 1

						test_results.append(
							TestResult(
								test_name=test_case_name,
								status="PASSED",
								exit_code=0,
								stdout=evaluator_stdout,
								stderr=evaluator_stderr
							)
						)


					# DONE Shell → TIMEOUT Python → WRONG_ANSWER
					# elif [ $exit_code -eq 124 ] || [ $exit_code -eq 2 ]; then
					# 	echo "[VERDICT] $test_case_name: TIMEOUT"
					elif exit_code in (124, 2):
						if not quiet:
							print(f"[VERDICT] {test_case_name}: TIMEOUT")

						test_results.append(
							TestResult(
								test_name=test_case_name,
								status="TIMEOUT",
								exit_code=exit_code,
								stdout=evaluator_stdout,
								stderr=evaluator_stderr
							)
						)

					# elif [ $exit_code -eq 3 ]; then
					# 	echo "[VERDICT] $test_case_name: RUNTIME_ERROR"
					elif exit_code == 3:
						if not quiet:
							print(f"[VERDICT] {test_case_name}: RUNTIME_ERROR")

						test_results.append(
							TestResult(
								test_name=test_case_name,
								status="RUNTIME_ERROR",
								exit_code=3,
								stdout=evaluator_stdout,
								stderr=evaluator_stderr
							)
						)

					# else
					# 	echo "[VERDICT] $test_case_name: WRONG_ANSWER"
					# fi
					else:
						if not quiet:
							print(f"[VERDICT] {test_case_name}: WRONG_ANSWER")

						test_results.append(
							TestResult(
								test_name=test_case_name,
								status="WRONG_ANSWER",
								exit_code=exit_code,
								stdout=evaluator_stdout,
								stderr=evaluator_stderr
							)
						)

				else:
					# # Standard Evaluation
					# run_standard "$input_item" "$expected_output" "$sandbox_dir" "$test_case_name"
					rc, test_result = run_standard(
						executable,
						input_item_path,
						expected_output,
						sandbox_dir,
						test_case_name,
						ext,
						timeout_sec,
						memory_cap_mb,
						sandbox,
						testcases_dir,
						question,
						quiet=quiet
					)

					# exit_code=$?
					# if [ $exit_code -eq 0 ]; then
					# 	PASSED=$((PASSED + 1))
					# fi
					if rc == 0:
						passed_tests += 1

					test_results.append(test_result)

				# if [ -n "$SAVE_OUTPUT_DIR" ]; then
				# 	mkdir -p "$SAVE_OUTPUT_DIR"
				# 	cp "$sandbox_dir/stdout.txt" "$SAVE_OUTPUT_DIR/${QUESTION}_output${test_case_name}.txt" 2>/dev/null || true
				# fi
				if save_output_dir:
					os.makedirs(save_output_dir, exist_ok=True)
					src_stdout = os.path.join(sandbox_dir, "stdout.txt")

					if os.path.isfile(src_stdout):
						shutil.copy2(
							src_stdout,
							os.path.join(
								save_output_dir,
								f"{question}_output{test_case_name}.txt"
							)
						)

			finally:
				# rm -rf "$sandbox_dir"
				shutil.rmtree(sandbox_dir, ignore_errors=True)

		# echo "[SCORE] $PASSED/$TOTAL"
		if not quiet:
			print(f"[SCORE] {passed_tests}/{total_tests}")

		return GradeResult(
			passed=passed_tests,
			total=total_tests,
			status="COMPLETED",
			tests=test_results
		)

	finally:
		shutil.rmtree(build_dir, ignore_errors=True)


def main():
	args = parse_arguments()

	result = grade(
		submission=args.submission,
		question=args.question,
		testcases_dir=args.testcases_dir,
		sandbox=args.sandbox,
		config_file=args.config,
		target_testcase=args.testcase,
		save_output_dir=args.save_output_dir,
		quiet=args.json
	)

	if args.json:
		print(json.dumps(result.to_dict(), indent=2))

	if result.status == "COMPLETED":
		return 0

	return 1


if __name__ == "__main__":
	sys.exit(main())
