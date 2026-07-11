#!/bin/bash
# ==============================================================================
# IndiGrader Pre-Created Setup Script
# ==============================================================================
# INSTRUCTIONS FOR INSTRUCTORS:
# 1. Duplicate this file and name it according to your course (e.g., CS101_setup.sh).
# 2. Update the COURSE_ID and DEFAULT_SERVER_URL variables below.
# 3. Distribute the file to students or serve it via your own static server.
#
# INSTRUCTIONS FOR STUDENTS:
# Run this script once at the start of the semester to install IndiGrader tools.
# Example: bash CS101_setup.sh
# ==============================================================================

COURSE_ID="COURSE_NAME_HERE"
DEFAULT_SERVER_URL="http://SERVER_IP_HERE:8000"

echo "Setting up IndiGrader for $COURSE_ID..."

mkdir -p ~/.local/bin
mkdir -p ~/.config/ig

echo "$DEFAULT_SERVER_URL" > ~/.config/ig/${COURSE_ID}.conf
echo "Server URL configured: $DEFAULT_SERVER_URL"

curl -s "$DEFAULT_SERVER_URL/clients/ig" -o ~/.local/bin/ig
chmod +x ~/.local/bin/ig
echo "CLI Tool installed."

cat << EOF > ~/.local/bin/${COURSE_ID}
#!/bin/bash
ig fetch "${COURSE_ID}" "\$@"
EOF
chmod +x ~/.local/bin/${COURSE_ID}
echo "Course Alias ($COURSE_ID) created."

if [[ ":\$PATH:" != *":\$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
    echo "Added ~/.local/bin to PATH in ~/.bashrc"
fi

echo "Setup Complete. To fetch your first lab, run: $COURSE_ID <lab_name>"
