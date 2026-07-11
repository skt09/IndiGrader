#!/bin/bash

if [ -z "$SERVER_URL" ]; then
    if [ -f ".ig_course/course_id" ]; then
        COURSE_ID=$(cat .ig_course/course_id)
        CONFIG_FILE="$HOME/.config/ig/${COURSE_ID}.conf"
        if [ -f "$CONFIG_FILE" ]; then
            SERVER_URL=$(cat "$CONFIG_FILE")
        fi
    fi
fi
SERVER_URL="${SERVER_URL:-http://127.0.0.1:8000}"

TOTAL_QUESTIONS=$(jq '.questions | length' .ig_course/config.json 2>/dev/null || echo 1)
total_obtained_marks=0

# Detect Roll No
ROLL_NO=""
for dir in */; do
    dir_name=$(basename "$dir")
    if [[ "$dir_name" =~ ^[a-zA-Z]{2}[0-9]{2}[a-zA-Z]{1}[0-9]{3}$ ]]; then
        ROLL_NO=$(echo "$dir_name" | tr '[:lower:]' '[:upper:]')
        break
    fi
done

if [ -z "$ROLL_NO" ]; then
    echo -e "\033[0;31mERROR: Could not find a valid Roll Number directory (e.g. CS25B012).\033[0m"
    echo "Make sure your code is inside a folder named with your roll number."
    exit 1
fi

echo -e "\033[1;36mAuto-detected Roll Number: $ROLL_NO\033[0m"

# --- Colors for better output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Dependencies
if ! command -v curl &> /dev/null; then
    echo -e "${RED}ERROR: 'curl' is not installed. Please install it to continue.${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}ERROR: 'jq' is not installed. Please install it to continue.${NC}"
    echo "Installation example:"
    echo "  - Ubuntu/Debian: sudo apt-get install jq"
    exit 1
fi

# Submit payload
process_question() {
    local Q_NO_NUM=$1
    local Q_NO="Q${Q_NO_NUM}"
    local ALLOWED_EXTS=("c" "cpp" "py" "awk")
    local FILE_PATH=""

    for ext in "${ALLOWED_EXTS[@]}"; do
        if [ -f "./${ROLL_NO}/${Q_NO}.${ext}" ]; then
            FILE_PATH="./${ROLL_NO}/${Q_NO}.${ext}"
            break
        elif [ -d "./${ROLL_NO}/${Q_NO}" ]; then
            echo -e "${YELLOW}Directory found for ${Q_NO}. Auto-tarring...${NC}"
            cd "./${ROLL_NO}" || exit 1
            tar --exclude="*.o" --exclude="*.out" --exclude="*.exe" --exclude="${Q_NO}_exec" -czf "${Q_NO}.tar.gz" "${Q_NO}"
            cd - > /dev/null
            FILE_PATH="./${ROLL_NO}/${Q_NO}.tar.gz"
            break
        fi
    done

    # Check if a valid file was found
    if [ -z "$FILE_PATH" ]; then
        echo -e "${RED}ERROR: Valid source file for ${Q_NO} (.c, .cpp, .py, .awk) not found in ./${ROLL_NO}/${NC}"
        return 1
    fi

    # Check if the file exists
    if [ ! -f "$FILE_PATH" ]; then
        echo -e "${RED}ERROR: File not found at '$FILE_PATH'${NC}"
        return 1
    fi

    # Check if late
    local END_TIME=$(jq -r '.end_time' .ig_course/config.json 2>/dev/null)
    local IS_LATE=false
    if [ -n "$END_TIME" ] && [ "$END_TIME" != "null" ]; then
        local CURRENT_SEC=$(date -u +%s)
        local END_SEC=$(date -u -d "$END_TIME" +%s 2>/dev/null)
        if [ -n "$END_SEC" ] && [ "$CURRENT_SEC" -gt "$END_SEC" ]; then
            echo -e "${YELLOW}You are late. Only one late submission is allowed.${NC}"
            echo -e "${YELLOW}Marks won't be considered during grading.${NC}"
            read -p "Do you really want to submit? (yes/no): " confirm
            if [ "$confirm" != "yes" ]; then
                echo "Submission cancelled."
                return 1
            fi
            IS_LATE=true
        fi
    fi

    # Transmit
    local CURL_CMD=(curl -s -X POST -F "roll=${ROLL_NO}" -F "file=@${FILE_PATH}")
    CURL_CMD+=("${SERVER_URL}/submit/${Q_NO}")
    
    local SUBMIT_RESPONSE=$("${CURL_CMD[@]}")

    if echo "$SUBMIT_RESPONSE" | grep -q "\"detail\""; then
        local ERR_MSG=$(echo "$SUBMIT_RESPONSE" | jq -r '.detail')
        echo -e "${RED}Server Error: ${ERR_MSG}${NC}"
        return 1
    fi

    local TASK_ID=$(echo "$SUBMIT_RESPONSE" | jq -r '.taskid')

    if [ -z "$TASK_ID" ] || [ "$TASK_ID" == "null" ]; then
        echo -e "${RED}Failed to submit. Server response:${NC}"
        echo "$SUBMIT_RESPONSE" | jq '.'
        return 1
    fi

    echo -e "${GREEN}Submission successful! Task ID: ${TASK_ID}${NC}\n"

    if [ "$IS_LATE" = true ]; then
        echo -e "${GREEN}Late submission is saved.${NC}"
        return 0
    fi

    # Poll
    local STATUS_RESPONSE
    while true; do
        STATUS_RESPONSE=$(curl -s "${SERVER_URL}/task-status/${TASK_ID}")
        local TASK_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')

        if [ "$TASK_STATUS" != "PENDING" ]; then
            echo -e "\n${GREEN}Task has completed with status: $TASK_STATUS${NC}"
            break
        fi
        
        echo -n "."
        sleep 2
    done

    # Process response
    echo -e "\n${BLUE}Final Result [${Q_NO}]${NC}"
    local TASK_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')

    if [ "$TASK_STATUS" != "SUCCESS" ]; then
        echo -e "${RED}The task failed to execute on the server.${NC}"
        echo "Server Response:"
        echo "$STATUS_RESPONSE" | jq '.'
        return 1
    fi

    local FINAL_RESULT=$(echo "$STATUS_RESPONSE" | jq '.result')
    local APP_STATUS=$(echo "$FINAL_RESULT" | jq -r '.status')

    if [[ "$APP_STATUS" == *"Compilation Error"* ]]; then
        echo -e "${RED}An error occurred during evaluation: ${APP_STATUS}${NC}"
        echo "Details:"
        echo "$FINAL_RESULT" | jq -r '.details'

    elif [ "$APP_STATUS" == "Finished" ]; then
        echo -e "${GREEN}Evaluation finished successfully!${NC}"

        local PASSED_COUNT=$(echo "$FINAL_RESULT" | jq -r '.passed')
        local FAILED_COUNT=$(echo "$FINAL_RESULT" | jq -r '.failed')
        local OBTAINED_MARKS=$(echo "$FINAL_RESULT" | jq -r '.marks')
        local QUESTION_FULL_MARKS=$(echo "$FINAL_RESULT" | jq -r '.full')

        echo -e "\n${BLUE}Test Case Details:${NC}"
        echo "$FINAL_RESULT" | jq -r '.results | keys[]' | while IFS= read -r test_name; do
            local VERDICT=$(echo "$FINAL_RESULT" | jq -r ".results[\"$test_name\"]")
            local FORMATTED_VERDICT=""
            case "$VERDICT" in
                "PASSED") FORMATTED_VERDICT="${GREEN}${VERDICT}${NC}" ;;
                "Time Limit Exceeded") FORMATTED_VERDICT="${YELLOW}${VERDICT}${NC}" ;;
                "Runtime Error") FORMATTED_VERDICT="${RED}${VERDICT} (e.g., SIGSEGV)${NC}" ;;
                "Wrong Answer") FORMATTED_VERDICT="${RED}${VERDICT}${NC}" ;;
                *) FORMATTED_VERDICT="${BLUE}${VERDICT}${NC}" ;;
            esac
            printf "  - %-20s %b\n" "$test_name:" "$FORMATTED_VERDICT"
        done

        echo -e "\n${BLUE}Summary for ${Q_NO}:${NC}"
        printf "  %-10s %b\n" "Passed:" "${GREEN}${PASSED_COUNT}${NC}"
        printf "  %-10s %b\n" "Failed:" "${RED}${FAILED_COUNT}${NC}"
        printf "  %-10s %b\n" "Marks:"  "${BLUE}${OBTAINED_MARKS} / ${QUESTION_FULL_MARKS}${NC}"

    elif [[ "$APP_STATUS" == *"Error"* ]]; then
        echo -e "${RED}An error occurred during evaluation: ${APP_STATUS}${NC}"
        echo "Details:"
        echo "$FINAL_RESULT" | jq '.'
    else
        echo -e "${YELLOW}Received an unknown status: ${APP_STATUS}${NC}"
        echo "Full Server Response:"
        echo "$STATUS_RESPONSE" | jq '.'
    fi
}

# --- Main Execution Logic ---
if [ "$#" -eq 0 ]; then
    echo -e "${BLUE}Processing all ${TOTAL_QUESTIONS} questions for Roll: ${ROLL_NO}${NC}"
    for (( i=1; i<=TOTAL_QUESTIONS; i++ )); do
        echo -e "\n${YELLOW}==================== Starting Question ${i} ====================${NC}"
        process_question "$i"
        echo -e "${YELLOW}==================== Finished Question ${i} ====================${NC}"
    done
elif [ "$#" -eq 1 ]; then
    process_question "$1"
else
    echo -e "${YELLOW}Usage: $0 [question_number]${NC}"
    echo "Example: $0 2"
    echo "If no question number is provided, all questions will be submitted."
    exit 1
fi
