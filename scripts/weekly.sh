#!/bin/bash
# Information Union - Weekly automated collection and analysis
# Runs every Monday at 8:00 AM

set -e

PROJECT_DIR="/Users/qiushui/Coding/Information-Union"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/weekly-$(date +%Y%m%d).log"

echo "=== Weekly run started at $(date) ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"
source "$VENV"

# 1. Collect data from all sources
echo "[$(date)] Collecting data..." >> "$LOG_FILE"
iu collect >> "$LOG_FILE" 2>&1

# 2. Summarize YouTube videos
echo "[$(date)] Summarizing videos..." >> "$LOG_FILE"
iu summarize >> "$LOG_FILE" 2>&1

# 3. Run AI analysis
echo "[$(date)] Running analysis..." >> "$LOG_FILE"
iu analyze >> "$LOG_FILE" 2>&1

# 4. Send email report
echo "[$(date)] Sending email..." >> "$LOG_FILE"
iu email >> "$LOG_FILE" 2>&1

echo "=== Weekly run completed at $(date) ===" >> "$LOG_FILE"
