#!/usr/bin/env bash
# Checkpoint management functions
# Provides atomic checkpoint file operations for stage recovery

CHECKPOINT_DIR=".checkpoints"

# Ensure checkpoint directory exists
mkdir -p "$CHECKPOINT_DIR"

# Write checkpoint with atomic operation
# Usage: write_checkpoint <stage_name> <status> [key1=value1 key2=value2 ...]
write_checkpoint() {
    local stage_name="$1"
    local status="$2"
    shift 2

    local checkpoint_file="${CHECKPOINT_DIR}/${stage_name}.checkpoint"

    # Create temporary file in same directory (ensures same filesystem for atomic mv)
    local tmp_file
    tmp_file=$(mktemp "${checkpoint_file}.XXXXXX")

    # Write checkpoint content
    {
        echo "stage=${stage_name}"
        echo "status=${status}"
        echo "timestamp=$(date -Iseconds)"

        # Optional additional fields
        for field in "$@"; do
            echo "$field"
        done
    } > "$tmp_file"

    # Atomic replace (mv is atomic within same filesystem)
    mv "$tmp_file" "$checkpoint_file"
}

# Read checkpoint status
# Usage: read_checkpoint <stage_name>
# Returns: status string (success/failed/running) or empty if not found
read_checkpoint() {
    local stage_name="$1"
    local checkpoint_file="${CHECKPOINT_DIR}/${stage_name}.checkpoint"

    if [[ ! -f "$checkpoint_file" ]]; then
        return 1
    fi

    # Validate required fields
    if ! grep -q "^status=" "$checkpoint_file"; then
        echo "[WARNING] Corrupted checkpoint: $checkpoint_file" >&2
        return 1
    fi

    # Extract and return status
    local status
    status=$(grep "^status=" "$checkpoint_file" | cut -d= -f2)
    echo "$status"
    return 0
}

# Check if stage is completed (both checkpoint and output files exist)
# Usage: check_stage_completed <stage_name>
# Returns: 0 if completed, 1 otherwise
check_stage_completed() {
    local stage="$1"

    # First check checkpoint status
    local checkpoint_status
    if checkpoint_status=$(read_checkpoint "$stage"); then
        if [[ "$checkpoint_status" != "success" ]]; then
            return 1
        fi
    else
        return 1
    fi

    # Then verify output files exist
    case "$stage" in
        data)
            # Check for non-empty JSONL files
            if [[ -d "outputs/data" ]]; then
                local file_count
                file_count=$(find outputs/data -name "*.jsonl" -type f ! -empty 2>/dev/null | wc -l)
                [[ $file_count -gt 0 ]] && return 0
            fi
            return 1
            ;;
        sft)
            # Check for adapter model file
            [[ -f "outputs/sft/final/adapter_model.safetensors" ]] && return 0
            return 1
            ;;
        grpo)
            # Check for final model directory
            if [[ -d "outputs/grpo/final" ]]; then
                # Verify it contains model files
                local model_files
                model_files=$(find outputs/grpo/final -type f -name "*.safetensors" -o -name "adapter_*.bin" 2>/dev/null | wc -l)
                [[ $model_files -gt 0 ]] && return 0
            fi
            return 1
            ;;
        *)
            echo "[WARNING] Unknown stage: $stage" >&2
            return 1
            ;;
    esac
}

# Clear checkpoint for a stage
# Usage: clear_checkpoint <stage_name>
clear_checkpoint() {
    local stage_name="$1"
    local checkpoint_file="${CHECKPOINT_DIR}/${stage_name}.checkpoint"

    if [[ -f "$checkpoint_file" ]]; then
        rm -f "$checkpoint_file"
        echo "[INFO] Cleared checkpoint for stage: $stage_name"
    fi
}
