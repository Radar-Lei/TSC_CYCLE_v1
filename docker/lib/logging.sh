#!/usr/bin/env bash
# Logging management functions
# Provides stage-based logging with dual output (console + file) and exit code preservation

LOG_DIR="logs"
DATE=""
CURRENT_LOG_FILE=""

# Initialize logging system
# Usage: init_logging
# Sets up log directory and date variable
init_logging() {
    mkdir -p "$LOG_DIR"
    DATE=$(date +%Y%m%d)
    echo "$LOG_DIR"
}

# Run command with logging
# Usage: run_with_logging <stage_name> <command> [args...]
# Logs to both console and logs/${DATE}-${stage_name}.log
# Returns: exit code of the command (not tee)
run_with_logging() {
    local stage_name="$1"
    shift

    local stage_log="${LOG_DIR}/${DATE}-${stage_name}.log"
    CURRENT_LOG_FILE="$stage_log"

    # Log command being executed
    {
        echo ""
        echo "=========================================="
        echo "Timestamp: $(date -Iseconds)"
        echo "Stage: ${stage_name}"
        echo "Command: $*"
        echo "=========================================="
        echo ""
    } | tee -a "$stage_log"

    # Execute command with dual output
    # Use PIPESTATUS to get exit code of command (index 0), not tee (index 1)
    "$@" 2>&1 | tee -a "$stage_log"
    local exit_code=${PIPESTATUS[0]}

    # Log completion status
    {
        echo ""
        echo "=========================================="
        echo "Stage: ${stage_name}"
        echo "Exit code: ${exit_code}"
        echo "Timestamp: $(date -Iseconds)"
        echo "=========================================="
        echo ""
    } | tee -a "$stage_log"

    return $exit_code
}

# Log info message
# Usage: log_info <message>
log_info() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_line="[INFO] ${timestamp} ${message}"

    echo "$log_line"

    # Also append to current log file if set
    if [[ -n "$CURRENT_LOG_FILE" ]]; then
        echo "$log_line" >> "$CURRENT_LOG_FILE"
    fi
}

# Log error message
# Usage: log_error <message>
log_error() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_line="[ERROR] ${timestamp} ${message}"

    echo "$log_line" >&2

    # Also append to current log file if set
    if [[ -n "$CURRENT_LOG_FILE" ]]; then
        echo "$log_line" >> "$CURRENT_LOG_FILE"
    fi
}

# Log stage start with visual separator
# Usage: log_stage_start <stage_name>
log_stage_start() {
    local stage_name="$1"
    local start_time
    start_time=$(date -Iseconds)

    local separator="=================================================="
    local header="=== Stage: ${stage_name} START ==="

    {
        echo ""
        echo "$separator"
        echo "$header"
        echo "Start time: ${start_time}"
        echo "$separator"
        echo ""
    } | tee -a "${LOG_DIR}/${DATE}-${stage_name}.log"

    # Store start time for duration calculation
    export "STAGE_START_TIME_${stage_name}=${start_time}"
}

# Log stage end with visual separator and duration
# Usage: log_stage_end <stage_name> <exit_code>
log_stage_end() {
    local stage_name="$1"
    local exit_code="$2"
    local end_time
    end_time=$(date -Iseconds)

    local separator="=================================================="
    local status="SUCCESS"
    [[ $exit_code -ne 0 ]] && status="FAILED"

    local header="=== Stage: ${stage_name} ${status} ==="

    {
        echo ""
        echo "$separator"
        echo "$header"
        echo "End time: ${end_time}"
        echo "Exit code: ${exit_code}"

        # Calculate duration if start time was recorded
        local start_var="STAGE_START_TIME_${stage_name}"
        if [[ -n "${!start_var}" ]]; then
            local start_epoch end_epoch duration
            start_epoch=$(date -d "${!start_var}" +%s 2>/dev/null)
            end_epoch=$(date -d "${end_time}" +%s 2>/dev/null)

            if [[ -n "$start_epoch" && -n "$end_epoch" ]]; then
                duration=$((end_epoch - start_epoch))
                local hours=$((duration / 3600))
                local minutes=$(((duration % 3600) / 60))
                local seconds=$((duration % 60))
                printf "Duration: %02d:%02d:%02d\n" $hours $minutes $seconds
            fi
        fi

        echo "$separator"
        echo ""
    } | tee -a "${LOG_DIR}/${DATE}-${stage_name}.log"
}
