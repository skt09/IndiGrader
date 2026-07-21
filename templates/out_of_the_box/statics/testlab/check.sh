#!/bin/bash

# Local Evaluation Script
# Usage: ./check.sh [question_number]

# Configuration
TESTCASES_DIR="testcases"
ACTUAL_OUTPUT_DIR="actual_output" 
CONFIG_PATH=".ig_course/config.json"
GRADE_SH_PATH="./grade.sh"
COMPILER="gcc"
COMPILER_FLAGS="-Wall"
LINKER_FLAGS="-lm"

# Color Codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Evaluation loop
grade_student() {
    local student_dir=$1
    local questions=("${@:2}")
    
    # Remove trailing slash for cleaner output
    local roll_number=$(basename "$student_dir")
    
    echo "=================================================="
    echo -e "${YELLOW}Grading submissions for: $roll_number${NC}"
    

    local student_log_dir="${student_dir}"

    for question in "${questions[@]}"; do
        echo -e "--- ${CYAN}[$roll_number] Grading Question: $question${NC} ---"
        
        local log_file="${student_log_dir}/${question}_log.txt"
        echo "Log for $roll_number - Question $question" > "$log_file"
        echo "----------------------------------------" >> "$log_file"

        local submission_file=""
        local question_digits=$(echo "$question" | tr -dc '0-9')
        local has_makefile="false"
        if [ -f "$CONFIG_PATH" ]; then
            has_makefile=$(jq -r ".\"$question\".makefile // false" "$CONFIG_PATH" 2>/dev/null)
        fi

        shopt -s nullglob
        for potential in "${student_dir}"*.{c,cpp,py,awk,sh} "${student_dir}"*/; do
            local clean_path="${potential%/}"
            local base_name=$(basename "$clean_path")
            if [ -f "$clean_path" ]; then
                base_name="${base_name%.*}"
            fi
            local base_name_digits=$(echo "$base_name" | tr -dc '0-9')
            if [[ -n "$base_name_digits" && "$base_name_digits" == "$question_digits" ]]; then
                if [ "$has_makefile" = "true" ]; then
                    if [ -d "$clean_path" ]; then
                        submission_file="$clean_path"
                        break
                    fi
                else
                    if [ -f "$clean_path" ]; then
                        submission_file="$clean_path"
                        break
                    fi
                fi
            fi
        done
        shopt -u nullglob

        if [ -z "$submission_file" ]; then
            echo -e "   ${RED}[$roll_number] Submission not found for $question.${NC}"
            echo "Error: Submission file not found." >> "$log_file"
            continue
        fi

        # Call grade.sh and parse its output line by line
        while IFS= read -r line; do
            echo "$line" >> "$log_file"
            
            if [[ "$line" == \[VERDICT\]* ]]; then
                # Parse [VERDICT] test01: PASSED
                test_info=$(echo "$line" | sed 's/^\[VERDICT\] //')
                test_name="${test_info%%: *}"
                verdict="${test_info#*: }"
                
                if [[ "$test_name" == "ALL" && "$verdict" == "COMPILATION_ERROR"* ]]; then
                    echo -e "   ${RED}[$roll_number] Compilation failed for $question.${NC}"
                elif [[ "$verdict" == PASSED* ]]; then
                    echo -e "${GREEN}  ${test_name}: PASSED${NC}"
                elif [[ "$verdict" == TIMEOUT* ]]; then
                    echo -e "${RED}  ${test_name}: FAILED (Timeout)${NC}"
                elif [[ "$verdict" == RUNTIME_ERROR* ]]; then
                    echo -e "${RED}  ${test_name}: FAILED (Runtime Error)${NC}"
                else
                    echo -e "${RED}  ${test_name}: FAILED (Wrong Answer)${NC}"
                fi
                
            elif [[ "$line" == \[SCORE\]* ]]; then
                score=$(echo "$line" | awk '{print $2}')
                passed=$(echo "$score" | cut -d'/' -f1)
                total=$(echo "$score" | cut -d'/' -f2)
                
                echo "=================================================="
                echo -e "${CYAN}Total Cases: ${total}${NC}"
                echo -e "${GREEN}Passed: ${passed}${NC}"
                echo -e "${RED}Failed: $((total - passed))${NC}"
                echo "=================================================="
                echo "----------------------------------------" >> "$log_file"
                echo "SUMMARY: Passed $passed / $total" >> "$log_file"
            elif [[ "$line" == \[LOG\]* ]]; then
                local log_text="${line#\[LOG\] }"
                if [[ "$log_text" == *"error"* || "$log_text" == *"failed"* || "$log_text" == *"Error"* || "$log_text" == *"Failed"* ]]; then
                    echo -e "      ${RED}${log_text}${NC}"
                else
                    echo -e "      ${log_text}"
                fi
            fi
        done < <("$GRADE_SH_PATH" --submission "$submission_file" --question "$question" --testcases_dir "$TESTCASES_DIR" --config "$CONFIG_PATH" ${TARGET_TESTCASE:+-t "$TARGET_TESTCASE"} --save_output_dir "$ACTUAL_OUTPUT_DIR")

    done
}

# --- Initial Setup ---
echo "Starting autograder..."
mkdir -p "$ACTUAL_OUTPUT_DIR"

questions=()

# --- Argument Parsing and Question Selection ---
if [ "$#" -eq 0 ]; then
    # No arguments provided, so find all question directories
    echo -e "${CYAN}Grading all available questions...${NC}"
    shopt -s nullglob
    question_dirs=("$TESTCASES_DIR"/*/)
    shopt -u nullglob

    if [ ${#question_dirs[@]} -eq 0 ]; then
        echo -e "${RED}Error: No question directories found in '$TESTCASES_DIR'. Please check your setup.${NC}"
        exit 1
    fi

    for q_dir in "${question_dirs[@]}"; do
        questions+=("$(basename "$q_dir")")
    done

elif [ "$#" -ge 1 ] && [ "$#" -le 2 ]; then
    # One or two arguments provided
    Q_TO_GRADE="Q$1"
    if [ ! -d "$TESTCASES_DIR/$Q_TO_GRADE" ]; then
        echo -e "${RED}Error: Test case directory for '$Q_TO_GRADE' not found in '$TESTCASES_DIR'.${NC}"
        exit 1
    fi
    if [ "$#" -eq 2 ]; then
        TARGET_TESTCASE="$2"
        echo -e "${CYAN}Grading only Question: $Q_TO_GRADE (Testcase: $TARGET_TESTCASE)${NC}"
    else
        TARGET_TESTCASE=""
        echo -e "${CYAN}Grading only Question: $Q_TO_GRADE${NC}"
    fi
    questions=("$Q_TO_GRADE")

else
    # Too many arguments
    echo -e "${YELLOW}Usage: $0 [question_number] [optional_testcase]${NC}"
    echo "Example to run only Q1: $0 1"
    echo "Example to run only Q1 testcase 4: $0 1 4"
    echo "Run without arguments to grade all questions."
    exit 1
fi

# --- Main Grading Loop ---
for student_dir in */; do
    # Skip non-submission directories
    if [[ "$student_dir" == "$TESTCASES_DIR/" || "$student_dir" == "$ACTUAL_OUTPUT_DIR/" ]]; then
        continue
    fi
    
    # Skip if it's not a directory or doesn't contain any supported source files (.c, .cpp, .py, .awk, .sh) or subdirectories
    has_source=false
    for ext in c cpp py awk sh; do
        if compgen -G "${student_dir}*.$ext" > /dev/null; then
            has_source=true
            break
        fi
    done
    if [ "$has_source" = false ]; then
        # Also check if there is any subdirectory (for makefile projects)
        if compgen -G "${student_dir}*/" > /dev/null; then
            has_source=true
        fi
    fi
    if ! [ -d "${student_dir}" ] || [ "$has_source" = false ]; then
        continue
    fi

    grade_student "$student_dir" "${questions[@]}"
done

echo -e "${GREEN}Grading complete. Student outputs are in '$ACTUAL_OUTPUT_DIR'.${NC}"
echo -e "${GREEN}Detailed logs are located inside each student's folder.${NC}"
