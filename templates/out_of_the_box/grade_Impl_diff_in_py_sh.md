I compared `grade.py` against the uploaded `grade.sh` as the reference, section by section. The important conclusion is:

**`grade.py` is structurally very close, but it is NOT functionally identical to `grade.sh` yet.**
The biggest mismatch is the output-diff logic, followed by custom evaluator behavior, testcase naming, static/hidden-file copying, and sandbox/memory/timeout semantics.

I am treating `grade.sh` as the reference you meant by `graph.sh`.  

## 1. Command-line argument handling

### `grade.sh`

It manually parses the arguments and then separately checks:

```bash
if [ -z "$SUBMISSION" ] || [ -z "$QUESTION" ] || [ -z "$TESTCASES_DIR" ]; then
```

Reference: 

### `grade.py`

Uses `argparse`:

```python
parser.add_argument("--submission", required=True)
parser.add_argument("--question", required=True)
parser.add_argument("--testcases_dir", required=True)
```

Reference: 

### Verdict

**Functionally equivalent for valid invocation.**

Minor difference: when required arguments are missing, Python's `argparse` error message/exit behavior is different from the shell script's `[LOG] Missing required arguments...`.

For grading functionality this is not significant.

---

# 2. Config-file handling

### Shell

`jq` independently extracts:

```bash
EVALUATOR=$(jq ...)
TIMEOUT_SEC=$(jq ...)
MEM_CAP_MB=$(jq ...)
MAKEFILE_MODE=$(jq ...)
EXEC_NAME=$(jq ...)
```

with defaults. 

### Python

Loads JSON and uses:

```python
q_config = config.get(question, {})
evaluator = q_config.get("evaluator", None)
timeout_sec = q_config.get("timeout", 5)
memory_cap_mb = q_config.get("memory_cap_mb", 512)
makefile_mode = q_config.get("makefile", False)
exec_name = q_config.get("executable_name", question)
```



### Important difference

Python preserves the JSON type.

For example, if the config accidentally contains:

```json
"makefile": "false"
```

then:

```python
if makefile_mode:
```

is **true**, because `"false"` is a non-empty string.

The shell version does:

```bash
if [ "$MAKEFILE_MODE" == "true" ];
```

so `"false"` is false.

### Verdict

**Equivalent only when config uses the expected JSON types**, e.g.

```json
"makefile": false,
"timeout": 5,
"memory_cap_mb": 512
```

For strict compatibility, Python should normalize these values.

---

# 3. Extension detection

Shell:

```bash
FILENAME=$(basename "$SUBMISSION")
EXT="${FILENAME##*.}"
...
EXT=".$EXT"
```



Python:

```python
filename = os.path.basename(args.submission)
name_part, ext = os.path.splitext(filename)
```



### Verdict

**Equivalent for normal files.**

One small edge-case difference exists for unusual filenames, but nothing important for `.c`, `.cpp`, `.py`, `.awk`.

---

# 4. Makefile projects

This is mostly equivalent.

Shell:

```bash
cp -r "$SUBMISSION"/* "$BUILD_DIR/"
```

Python:

```python
shutil.copytree(args.submission, build_dir, dirs_exist_ok=True)
```

 

## Important difference: hidden files

Shell's:

```bash
"$SUBMISSION"/*
```

does **not** copy `.gitignore`, `.env`, `.config`, etc.

Python `copytree()` **does copy hidden files**.

The same difference exists for testcase static directories.

### Example

Submission:

```text
submission/
├── Makefile
├── main.c
└── .config
```

Shell:

```text
main.c
Makefile
```

Python:

```text
main.c
Makefile
.config
```

So the Python version is more complete/OS-flexible, but **not exactly behaviorally identical**.

### My recommendation

For exact equivalence, Python should deliberately emulate the shell's non-hidden glob behavior.

For a better cross-platform grader, I would instead keep Python's behavior because copying hidden project files is generally safer and more correct.

---

# 5. C compilation

Shell:

```bash
gcc $CFLAGS "$SUBMISSION" $LDFLAGS -o "$EXECUTABLE"
```

Python:

```python
subprocess.run(
    ["gcc"] + CFLAGS + [args.submission] + LDFLAGS + ["-o", executable]
)
```

Reference:  

### Verdict

**Functionally equivalent**, and Python's list-based invocation is actually safer because shell word splitting is avoided.

Same flags:

```text
-Wall
-lm
-lpthread
```

---

# 6. C++ compilation

Same conclusion.

Shell:

```bash
g++ $CXXFLAGS "$SUBMISSION" $LDFLAGS
```

Python:

```python
["g++"] + CXXFLAGS + [args.submission] + LDFLAGS
```

 

**Equivalent for normal environments.**

---

# 7. Make executable path absolute

Shell:

```bash
if [[ ! "$EXECUTABLE" == /* ]]; then
    EXECUTABLE="$PWD/$EXECUTABLE"
fi
```

Python:

```python
if not os.path.isabs(executable):
    executable = os.path.abspath(executable)
```

 

### Verdict

**Python is more OS-correct.**

The shell specifically assumes Unix absolute paths beginning with `/`.

Python correctly handles Windows drive paths such as:

```text
C:\Users\...
```

This is one place where the Python version improves portability without changing intended grader behavior.

---

# 8. Global static injection

Both implement:

```text
testcases/<question>/static/
        ↓
sandbox
```

Shell uses `cp`, Python uses `copy2/copytree`.  

### Difference

Again, Python copies hidden files while the shell's `*` does not.

Also Python explicitly handles directories recursively.

### Verdict

**Intended functionality same, exact filesystem behavior different.**

---

# 9. Directory-mode testcase handling

Shell:

```bash
if [ -d "$input_item" ]; then
    cp -r "$input_item/"* "$sandbox_dir/"
```

Then detects:

```text
stdin.txt
args.txt
```



Python does the same conceptual operation with `os.listdir()` and `copytree/copy2`.



### Difference

Again:

**Python copies hidden files.**

Shell does not.

---

# 10. Args-only testcase detection

This is a real behavioral difference.

Shell:

```bash
elif [[ "$input_item" == *args*.txt ]]; then
```

Python:

```python
elif "args" in os.path.basename(input_item) and input_item.endswith(".txt"):
```

### Why this is almost equivalent

For normal testcase names like:

```text
args01.txt
args4.txt
myargs02.txt
```

both recognize it.

But shell checks the **whole path**, while Python checks only the basename for `"args"`.

Usually this won't matter because the testcase directory itself doesn't contain `args`.

### Verdict

**Practically equivalent for normal layout.**

---

# 11. Stdin-only mode

Both resolve the input file and provide it to stdin.

Shell uses:

```bash
stdin_file="$PWD/$input_item"
```

when relative.

Python uses:

```python
stdin_file = os.path.abspath(input_item)
```

 

### Verdict

**Equivalent.**

---

# 12. Executable copied into sandbox

Shell:

```bash
local local_exec=$(basename "$EXECUTABLE")
cp -r "$EXECUTABLE" "$sandbox_dir/"
```

Python:

```python
local_exec = os.path.basename(executable)
dest_exec = os.path.join(sandbox_dir, local_exec)

if os.path.isdir(executable):
    shutil.copytree(...)
else:
    shutil.copy2(...)
```

 

### Verdict

**Intended behavior is equivalent.**

Python handles the destination more explicitly.

---

# 13. Firejail / sandbox

Reference:

```bash
if [ "$SANDBOX" = true ]; then
    CMD=("firejail" "--quiet" "--noprofile" "--private=.")
fi
```



Python:

```python
if sandbox_flag and os.name == 'posix' and shutil.which("firejail"):
    cmd += ["firejail", "--quiet", "--noprofile", "--private=."]
```



### This is deliberately different.

Suppose Linux + `--sandbox` is supplied but Firejail isn't installed.

### Shell

Attempts:

```text
firejail ...
```

and gets an execution error.

### Python

Simply doesn't use Firejail.

So Python turns:

```text
sandbox requested + firejail unavailable
```

into:

```text
normal execution
```

rather than:

```text
sandbox execution failure
```

### Verdict

**Not equivalent.**

But for your stated goal — **OS flexibility** — the Python behavior is more user-friendly.

However, from a security perspective, this can be dangerous: requesting sandboxing and silently running unsandboxed is not ideal.

A better Python behavior would be:

```text
--sandbox + Firejail unavailable
        ↓
explicit warning / error
```

rather than silently disabling sandboxing.

---

# 14. Python/AWK/executable invocation

Shell:

```bash
if [[ "$EXT" == ".py" ]]; then
    python3 "./$local_exec"
elif [[ "$EXT" == ".awk" ]]; then
    awk -f "./$local_exec"
else
    "./$local_exec"
fi
```



Python:

```python
if ext == ".py":
    cmd += ["python3" if os.name != 'nt' else "python", ...]
elif ext == ".awk":
    cmd += ["awk", "-f", ...]
else:
    ...
```



### Verdict

**Python improves portability.**

On Windows:

```text
python
```

instead of:

```text
python3
```

That is a good change.

---

# 15. Argument parsing from `args.txt`

Shell:

```bash
EXTRA_ARGS=($(cat "$args_file"))
```

Python:

```python
extra_args = f.read().split()
```

 

### Verdict

For ordinary whitespace-separated command arguments:

**Equivalent.**

Neither preserves shell-style quoting such as:

```text
--name "John Smith"
```

as one argument.

---

# 16. Working directory

Shell:

```bash
cd "$sandbox_dir"
```

Python:

```python
orig_cwd = os.getcwd()
os.chdir(sandbox_dir)
...
os.chdir(orig_cwd)
```

 

### Verdict

**Equivalent in intent.**

Python's `finally` makes restoration more reliable.

---

# 17. MEMORY LIMIT — important difference

Shell:

```bash
ulimit -v "$((MEM_CAP_MB * 1024))"
```



Python:

```python
resource.setrlimit(
    resource.RLIMIT_AS,
    (memory_cap_mb * 1024 * 1024, resource.RLIM_INFINITY)
)
```



These are conceptually similar on Linux, but **not exactly equivalent**.

## Problem in Python

You're requesting:

```text
soft = memory limit
hard = infinity
```

If the current hard RLIMIT_AS is already finite, increasing it to infinity may fail.

Your code silently does:

```python
except Exception:
    pass
```

meaning the memory limit can simply disappear.

So:

```text
grade.sh
    → memory limit applied

grade.py
    → memory limit may NOT be applied
```

### This should be fixed.

The Python implementation should inspect the current limit and safely reduce it rather than blindly trying to increase the hard limit.

---

# 18. TIMEOUT behavior

Shell:

```bash
timeout "${TIMEOUT_SEC}s" ...
```

and recognizes:

```bash
exit_code == 124
```



Python:

```python
subprocess.run(..., timeout=timeout_sec)
```

and catches:

```python
except subprocess.TimeoutExpired:
```



### Verdict

For the normal testcase:

**Both produce TIMEOUT.**

But process-tree behavior can differ.

`timeout` and Python's `subprocess.run(timeout=...)` do not necessarily kill an entire descendant process tree in exactly the same way.

So strictly:

**not bit-for-bit equivalent process management.**

---

# 19. Execution time shown in verdict

This is another definite difference.

Shell:

```bash
/usr/bin/time -f "%e" -o "time.txt"
```

Reference: 

Python:

```python
start_time = time.time()
...
exec_time = round(time.time() - start_time, 2)
```



### Differences

Shell:

```text
0.013
```

Python:

```text
0.01
```

Also if `/usr/bin/time` isn't present, the shell leaves the execution time blank.

Python always generates a time.

### Verdict

**Not exactly equivalent**, but functionally harmless.

---

# 20. Runtime-error handling

Shell:

```bash
if [ $exit_code -ne 0 ]; then
    ...
    return 3
fi
```

Python:

```python
elif exit_code != 0:
    ...
    return 3
```

 

### Verdict

**Equivalent for ordinary failures.**

---

# 21. CRITICAL: output comparison is NOT equivalent

This is the largest functional issue.

## `grade.sh`

Defines:

```bash
DIFF_FLAGS="-i -w -B"
```

and:

```bash
diff $DIFF_FLAGS "$actual_output" "$expected_output"
```

 

Meaning:

### `-i`

Ignore case.

```text
Hello
hello
```

→ PASS

### `-w`

Ignore all whitespace differences.

```text
1  2  3
1 2 3
```

→ PASS

### `-B`

Ignore blank lines.

```text
1
2
```

and

```text
1

2
```

→ PASS

---

## `grade.py`

Uses:

```python
lines1 = [line.strip() for line in f1 if line.strip()]
lines2 = [line.strip() for line in f2 if line.strip()]
return lines1 == lines2
```



This only:

* removes leading whitespace
* removes trailing whitespace
* removes completely blank lines

It does **NOT**:

* ignore case
* ignore internal whitespace

### Example 1

Expected:

```text
Hello World
```

Actual:

```text
hello world
```

Shell → **PASS**

Python → **WRONG ANSWER**

### Example 2

Expected:

```text
10 20
```

Actual:

```text
10    20
```

Shell → **PASS**

Python → **WRONG ANSWER**

### Example 3

Expected:

```text
10 20
```

Actual:

```text
1020
```

Shell → **WRONG ANSWER**

Python → **WRONG ANSWER**

So Python is stricter.

## This MUST be changed for exact grading equivalence.

---

# 22. Diff snippet

Shell:

```bash
diff -u --color=always ... | head -n 15
```

Python:

```python
difflib.unified_diff(...)
```

 

### Verdict

Both provide a unified diff, but formatting is not identical.

This does **not** affect score, only diagnostic output.

---

# 23. Testcase ordering

Shell:

```bash
for input_item in "$Q_INPUT_DIR"/*;
```

Python:

```python
input_items = sorted(os.listdir(q_input_dir))
```

 

Python is more deterministic.

### Verdict

Test execution **order may differ**, but total pass/fail should normally remain the same.

---

# 24. IMPORTANT: testcase name generation differs

Shell:

```bash
test_case_name=$(basename "$input_item" | sed -e 's/^input//' -e 's/^args//')
```

Notice that **both substitutions are performed sequentially**.

Python:

```python
if test_case_name.startswith("input"):
    test_case_name = test_case_name[5:]
elif test_case_name.startswith("args"):
    test_case_name = test_case_name[4:]
```

This means Python performs **only one** prefix removal.

### Example

Input filename:

```text
inputargs04.txt
```

Shell:

```text
inputargs04.txt
→ args04.txt
→ 04.txt
→ 04
```

Python:

```text
inputargs04.txt
→ args04.txt
→ stops
→ args04
```

That's a genuine functionality mismatch.

For normal testcase names such as:

```text
input01
input02
args03
```

you won't see it.

But for exact equivalence, Python should reproduce the shell's sequential behavior.

---

# 25. Targeted testcase matching

Shell strips leading zeros:

```bash
sed 's/^0*//'
```

Python:

```python
s.lstrip('0')
```

 

### Verdict

**Equivalent.**

For example:

```text
-t 4
```

matches:

```text
input04
```

---

# 26. Expected output `.txt` fallback

Both do:

```text
outputX
```

then:

```text
outputX.txt
```

if necessary.

 

### Verdict

**Equivalent.**

---

# 27. Custom evaluator — major difference

Shell:

```bash
EVAL_SCRIPT="$(cd $(dirname "$CONFIG_FILE") && pwd)/$EVALUATOR"

if [ ! -x "$EVAL_SCRIPT" ]; then
    chmod +x "$EVAL_SCRIPT"
fi

"$EVAL_SCRIPT" ...
```



Python:

```python
eval_script = os.path.abspath(
    os.path.join(os.path.dirname(args.config), evaluator)
)
...
res = subprocess.run(eval_cmd)
```



## Difference 1 — Python doesn't chmod

If evaluator exists but isn't executable:

### Shell

```text
chmod +x
→ execute
```

### Python

```text
PermissionError
→ grader can crash
```

So this is a real mismatch.

---

# 28. Custom evaluator timeout code — VERY important

Shell recognizes:

```bash
elif [ $exit_code -eq 124 ] || [ $exit_code -eq 2 ]; then
    echo "... TIMEOUT"
```



Python recognizes only:

```python
elif exit_code == 2:
    print("TIMEOUT")
```



### Therefore

If evaluator returns:

```text
124
```

Shell → **TIMEOUT**

Python → **WRONG_ANSWER**

This definitely needs correction.

---

# 29. Custom evaluator paths

The basic argument order is the same:

```text
EXECUTABLE
input_item
expected_output
sandbox_dir
TIMEOUT
SANDBOX
```

Shell: 

Python: 

### Verdict

**Equivalent for normal evaluator usage.**

Python's path resolution is cleaner.

---

# 30. Testcase loop and hidden files

Shell:

```bash
for input_item in "$Q_INPUT_DIR"/*
```

doesn't include dotfiles.

Python:

```python
os.listdir(q_input_dir)
```

does.

Therefore if you ever have:

```text
.input01
```

Python will attempt to grade it while shell won't.

Again, probably irrelevant in your existing testcase structure, but not identical.

---

# 31. Save-output behavior

Both save:

```text
<Question>_output<Testcase>.txt
```

Python checks whether stdout exists before copying. Shell tries the copy and suppresses errors.

 

### Verdict

**Effectively equivalent.**

---

# 32. Cleanup

Shell:

```bash
rm -rf "$sandbox_dir"
trap 'rm -rf "$BUILD_DIR"' EXIT
```

Python:

```python
shutil.rmtree(sandbox_dir, ignore_errors=True)
...
shutil.rmtree(build_dir, ignore_errors=True)
```

 

### Verdict

**Equivalent intended behavior.**

Python's `finally` structure is arguably more robust.

---

# Final compatibility assessment

| Area                                   | `grade.py` vs `grade.sh`      |
| -------------------------------------- | ----------------------------- |
| CLI arguments                          | ✅                             |
| Config defaults                        | ✅ mostly                      |
| Extension detection                    | ✅                             |
| C compilation                          | ✅                             |
| C++ compilation                        | ✅                             |
| Makefile compilation                   | ✅ mostly                      |
| Static file injection                  | ⚠️ hidden files differ        |
| Directory testcases                    | ✅ mostly                      |
| Args-only mode                         | ✅ mostly                      |
| Python/AWK execution                   | ✅, Python is more OS-flexible |
| Argument loading                       | ✅                             |
| Working directory                      | ✅                             |
| Memory limit                           | ⚠️ **not exactly equivalent** |
| Timeout                                | ⚠️ process behavior differs   |
| Runtime errors                         | ✅                             |
| Output comparison                      | ❌ **major mismatch**          |
| Diff display                           | ⚠️ cosmetic difference        |
| Test ordering                          | ⚠️ different                  |
| Testcase-name parsing                  | ❌ edge-case mismatch          |
| Targeted testcase                      | ✅                             |
| Expected-output fallback               | ✅                             |
| Custom evaluator invocation            | ✅ mostly                      |
| Custom evaluator executable permission | ❌                             |
| Custom evaluator timeout 124           | ❌                             |
| Output saving                          | ✅                             |
| Cleanup                                | ✅                             |

## The 5 things I would fix before calling `grade.py` a drop-in replacement

### 1. Reproduce `diff -i -w -B`

This is the biggest one.

Python comparison should emulate:

```bash
diff -i -w -B
```

not merely:

```python
line.strip()
```

A robust OS-independent implementation can normalize:

```text
case
all whitespace
blank lines
```

before comparison.

---

### 2. Fix testcase-name stripping

Change the Python logic from:

```python
if startswith("input"):
    ...
elif startswith("args"):
    ...
```

to sequential stripping equivalent to:

```bash
sed -e 's/^input//' -e 's/^args//'
```

because the shell applies both transformations.

---

### 3. Custom evaluator: handle exit code 124

Python should use:

```python
elif exit_code in (124, 2):
    ...
```

to match the shell exactly.

---

### 4. Custom evaluator: handle executable permission

Before executing an evaluator on POSIX, emulate:

```bash
chmod +x
```

or invoke it using an appropriate interpreter.

---

### 5. Make memory limiting reliable

The current:

```python
resource.setrlimit(
    resource.RLIMIT_AS,
    (limit, resource.RLIM_INFINITY)
)
```

can fail and then silently disable the limit.

That is not safe for a grader.

---

# Most important conceptual point

Your current Python version is **not simply a line-by-line translation** of `grade.sh`.

It is actually a mixture of:

```text
grade.sh semantics
        +
Python implementation changes
        +
some OS-portability improvements
        +
some accidental behavioral differences
```

The good news is that the overall architecture is correct: argument parsing → config → build → sandbox → testcase handling → evaluator/standard execution → verdict → score. The core flow matches the reference very closely. 

But I would **not yet call it "functionality exactly the same"**, particularly because of the `diff -i -w -B` mismatch and custom-evaluator `124` mismatch.

The next logical step is to make `grade.py` a **behaviorally compatible implementation of `grade.sh` while retaining its cross-platform improvements**, rather than making it merely "similar."
