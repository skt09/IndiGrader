#!/bin/bash

# Unified Grader

SUBMISSION=""
QUESTION=""
TESTCASES_DIR=""
SANDBOX=false
CONFIG_FILE="config.json"
TARGET_TESTCASE=""

# Standardized Flags
CFLAGS="-Wall"
CXXFLAGS="-Wall"
LDFLAGS="-lm -lpthread"
DIFF_FLAGS="-i -w -B"


# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --submission) SUBMISSION="$2"; shift ;;
        --question) QUESTION="$2"; shift ;;
        --testcases_dir) TESTCASES_DIR="$2"; shift ;;
        --sandbox) SANDBOX=true ;;
        --config) CONFIG_FILE="$2"; shift ;;
        -t|--testcase) TARGET_TESTCASE="$2"; shift ;;
        *) echo "[LOG] Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$SUBMISSION" ] || [ -z "$QUESTION" ] || [ -z "$TESTCASES_DIR" ]; then
    echo "[LOG] Missing required arguments: --submission, --question, --testcases_dir"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[LOG] Config file not found: $CONFIG_FILE"
    exit 1
fi

# Load config
EVALUATOR=$(jq -r ".\"$QUESTION\".evaluator // empty" "$CONFIG_FILE" 2>/dev/null)
TIMEOUT_SEC=$(jq -r ".\"$QUESTION\".timeout // 5" "$CONFIG_FILE" 2>/dev/null)
MEM_CAP_MB=$(jq -r ".\"$QUESTION\".memory_cap_mb // 512" "$CONFIG_FILE" 2>/dev/null)

# Detect extension
FILENAME=$(basename "$SUBMISSION")
EXT="${FILENAME##*.}"
if [[ "$FILENAME" == "$EXT" ]]; then
    EXT=""
else
    EXT=".$EXT"
fi

# Compilation step (if not using custom evaluator that handles compilation)
# Actually, we should compile if it's .c or .cpp
EXECUTABLE="$SUBMISSION"
if [[ "$EXT" == ".c" ]]; then
    EXECUTABLE="${SUBMISSION%.c}_exec"
    echo "[LOG] Compiling C source..."
    if ! gcc $CFLAGS "$SUBMISSION" $LDFLAGS -o "$EXECUTABLE" 2> "${SUBMISSION}_compile_err.txt"; then
        echo "[LOG] Compilation failed:"
        cat "${SUBMISSION}_compile_err.txt" | while read -r line; do echo "[LOG] $line"; done
        echo "[VERDICT] ALL: COMPILATION_ERROR"
        exit 1
    fi
elif [[ "$EXT" == ".cpp" ]]; then
    EXECUTABLE="${SUBMISSION%.cpp}_exec"
    echo "[LOG] Compiling C++ source..."
    if ! g++ $CXXFLAGS "$SUBMISSION" $LDFLAGS -o "$EXECUTABLE" 2> "${SUBMISSION}_compile_err.txt"; then
        echo "[LOG] Compilation failed:"
        cat "${SUBMISSION}_compile_err.txt" | while read -r line; do echo "[LOG] $line"; done
        echo "[VERDICT] ALL: COMPILATION_ERROR"
        exit 1
    fi
fi

# Make EXECUTABLE absolute if it's not already
if [[ ! "$EXECUTABLE" == /* ]]; then
    EXECUTABLE="$PWD/$EXECUTABLE"
fi

# Execution function
run_standard() {
    local input_item="$1"
    local expected_output="$2"
    local sandbox_dir="$3"
    local test_name="$4"

    if [[ ! "$expected_output" == /* ]]; then
        expected_output="$PWD/$expected_output"
    fi

    mkdir -p "$sandbox_dir"
    local actual_output="$sandbox_dir/stdout.txt"

    # Global Static Injection
    if [ -d "$TESTCASES_DIR/$QUESTION/static" ]; then
        cp -r "$TESTCASES_DIR/$QUESTION/static/"* "$sandbox_dir/" 2>/dev/null || true
    fi

    local stdin_file="/dev/null"
    local args_file="/dev/null"

    if [ -d "$input_item" ]; then
        # Directory Mode (Hybrid)
        cp -r "$input_item/"* "$sandbox_dir/" 2>/dev/null || true
        if [ -f "$sandbox_dir/stdin.txt" ]; then
            stdin_file="$sandbox_dir/stdin.txt"
        fi
        if [ -f "$sandbox_dir/args.txt" ]; then
            args_file="$sandbox_dir/args.txt"
        fi
    elif [[ "$input_item" == *args*.txt ]]; then
        # Arg-only Mode
        if [[ ! "$input_item" == /* ]]; then
            args_file="$PWD/$input_item"
        else
            args_file="$input_item"
        fi
    else
        # Stdin-only Mode
        if [[ ! "$input_item" == /* ]]; then
            stdin_file="$PWD/$input_item"
        else
            stdin_file="$input_item"
        fi
    fi

    # Copy executable/source to sandbox_dir so firejail can access it
    local local_exec=$(basename "$EXECUTABLE")
    cp -r "$EXECUTABLE" "$sandbox_dir/"

    # Command array construction
    local CMD=()
    if [ "$SANDBOX" = true ]; then
        CMD=("firejail" "--quiet" "--noprofile" "--private=.")
    fi

    if [[ "$EXT" == ".py" ]]; then
        CMD+=("python3" "./$local_exec")
    elif [[ "$EXT" == ".awk" ]]; then
        CMD+=("awk" "-f" "./$local_exec")
    else
        CMD+=("./$local_exec")
    fi

    # Load args
    local EXTRA_ARGS=()
    if [ -f "$args_file" ]; then
        EXTRA_ARGS=($(cat "$args_file"))
    fi

    # Run command
    cd "$sandbox_dir" || exit 1
    # Enforce memory limit and measure time
    (
        ulimit -v "$((MEM_CAP_MB * 1024))"
        /usr/bin/time -f "%e" -o "time.txt" timeout "${TIMEOUT_SEC}s" "${CMD[@]}" "${EXTRA_ARGS[@]}" < "$stdin_file" > "stdout.txt" 2> "stderr.txt"
    )
    local exit_code=$?
    local exec_time=""
    if [ -f "time.txt" ]; then
        exec_time=$(cat "time.txt")
    fi
    cd - >/dev/null

    if [ $exit_code -eq 124 ]; then
        echo "[VERDICT] $test_name: TIMEOUT (${exec_time}s)"
        return 2
    elif [ $exit_code -ne 0 ]; then
        echo "[VERDICT] $test_name: RUNTIME_ERROR (${exec_time}s)"
        echo "[LOG] Exit code $exit_code. Stderr:"
        cat "$sandbox_dir/stderr.txt" | while read -r line; do echo "[LOG] $line"; done
        return 3
    fi

    # Diff
    if diff $DIFF_FLAGS "$actual_output" "$expected_output" > /dev/null 2>&1; then
        echo "[VERDICT] $test_name: PASSED (${exec_time}s)"
        return 0
    else
        echo "[VERDICT] $test_name: WRONG_ANSWER (${exec_time}s)"
        echo "[LOG] Diff snippet (Expected vs Actual):"
        diff -u --color=always "$expected_output" "$actual_output" | head -n 15 | while read -r line; do echo "[LOG] $line"; done
        return 1
    fi
}

# Run tests
TOTAL=0
PASSED=0

# Ensure testcases dir exists
Q_INPUT_DIR="$TESTCASES_DIR/$QUESTION/input"
Q_OUTPUT_DIR="$TESTCASES_DIR/$QUESTION/output"

if [ ! -d "$Q_INPUT_DIR" ]; then
    echo "[LOG] No input directory found at $Q_INPUT_DIR"
    exit 1
fi

shopt -s nullglob
for input_item in "$Q_INPUT_DIR"/*; do
    [ -e "$input_item" ] || continue
    
    test_case_name=$(basename "$input_item" | sed -e 's/^input//' -e 's/^args//')
    if [[ "$test_case_name" == *.txt ]]; then
        test_case_name="${test_case_name%.txt}"
    fi

    # Targeted testcase filter
    if [ -n "$TARGET_TESTCASE" ]; then
        # Strip leading zeros for a fair numerical comparison (so 4 == 04)
        stripped_target=$(echo "$TARGET_TESTCASE" | sed 's/^0*//')
        stripped_current=$(echo "$test_case_name" | sed 's/^0*//')
        if [ "$stripped_current" != "$stripped_target" ]; then
            continue
        fi
    fi
    
    TOTAL=$((TOTAL + 1))

    expected_output="$Q_OUTPUT_DIR/output${test_case_name}"
    # Might be a .txt or a directory
    if [ ! -e "$expected_output" ] && [ -e "${expected_output}.txt" ]; then
        expected_output="${expected_output}.txt"
    fi

    sandbox_dir=$(mktemp -d -t sandbox_XXXXXX)
    
    # Evaluate
    if [ -n "$EVALUATOR" ] && [ "$EVALUATOR" != "null" ]; then
        # Custom Evaluation
        # Resolve to absolute paths if evaluator assumes it
        EVAL_SCRIPT="$(cd $(dirname "$CONFIG_FILE") && pwd)/$EVALUATOR"
        if [ ! -x "$EVAL_SCRIPT" ]; then
            chmod +x "$EVAL_SCRIPT"
        fi
        
        # Pass EXECUTABLE, input_item, expected_output, sandbox_dir, timeout, sandbox_flag
        "$EVAL_SCRIPT" "$EXECUTABLE" "$input_item" "$expected_output" "$sandbox_dir" "$TIMEOUT_SEC" "$SANDBOX"
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "[VERDICT] $test_case_name: PASSED"
            PASSED=$((PASSED + 1))
        elif [ $exit_code -eq 124 ] || [ $exit_code -eq 2 ]; then
            echo "[VERDICT] $test_case_name: TIMEOUT"
        elif [ $exit_code -eq 3 ]; then
            echo "[VERDICT] $test_case_name: RUNTIME_ERROR"
        else
            echo "[VERDICT] $test_case_name: WRONG_ANSWER"
        fi
    else
        # Standard Evaluation
        run_standard "$input_item" "$expected_output" "$sandbox_dir" "$test_case_name"
        exit_code=$?
        if [ $exit_code -eq 0 ]; then
            PASSED=$((PASSED + 1))
        fi
    fi

    rm -rf "$sandbox_dir"
done
shopt -u nullglob

echo "[SCORE] $PASSED/$TOTAL"

