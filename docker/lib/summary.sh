#!/usr/bin/env bash
# Stage summary functions
# Provides formatted summaries for different training stages

# Format duration from seconds to HH:MM:SS
# Usage: format_duration <seconds>
format_duration() {
    local total_seconds="$1"
    local hours=$((total_seconds / 3600))
    local minutes=$(((total_seconds % 3600) / 60))
    local seconds=$((total_seconds % 60))
    printf "%02d:%02d:%02d" $hours $minutes $seconds
}

# Show stage-specific summary
# Usage: show_stage_summary <stage_name>
show_stage_summary() {
    local stage_name="$1"

    local separator="=========================================="
    echo ""
    echo "$separator"
    echo "=== ${stage_name} Stage Complete ==="
    echo "$separator"

    case "$stage_name" in
        data)
            show_data_summary
            ;;
        sft)
            show_sft_summary
            ;;
        grpo)
            show_grpo_summary
            ;;
        *)
            echo "[WARNING] Unknown stage: $stage_name"
            ;;
    esac

    echo "$separator"
    echo ""
}

# Show data generation stage summary
show_data_summary() {
    local data_dir="outputs/data"

    if [[ ! -d "$data_dir" ]]; then
        echo "Output directory not found: $data_dir"
        return
    fi

    # Count generated files
    local file_count
    file_count=$(find "$data_dir" -name "*.jsonl" -type f 2>/dev/null | wc -l)

    echo "Generated files: $file_count"

    # Count total samples (lines in JSONL files)
    if [[ $file_count -gt 0 ]]; then
        local total_lines=0
        while IFS= read -r file; do
            local lines
            lines=$(wc -l < "$file" 2>/dev/null || echo 0)
            total_lines=$((total_lines + lines))
        done < <(find "$data_dir" -name "*.jsonl" -type f 2>/dev/null)

        echo "Total samples: $total_lines"
    else
        echo "Total samples: 0"
    fi

    # Total size
    local total_size
    total_size=$(du -sh "$data_dir" 2>/dev/null | cut -f1)
    echo "Total size: ${total_size:-N/A}"

    echo "Output directory: $data_dir"
}

# Show SFT training stage summary
show_sft_summary() {
    local sft_model_dir="outputs/sft/final"
    local log_file="${LOG_DIR}/${DATE}-sft.log"

    # Extract final loss from log
    if [[ -f "$log_file" ]]; then
        # Try multiple loss patterns
        local final_loss
        final_loss=$(grep -oP '(?:loss[=:\s]+|"loss":\s*)[\d.]+' "$log_file" 2>/dev/null | grep -oP '[\d.]+' | tail -1)

        if [[ -n "$final_loss" ]]; then
            echo "Final loss: $final_loss"
        else
            echo "Final loss: N/A (not found in log)"
        fi
    else
        echo "Final loss: N/A (log file not found)"
    fi

    # Model path and size
    if [[ -f "${sft_model_dir}/adapter_model.safetensors" ]]; then
        echo "Model path: ${sft_model_dir}/adapter_model.safetensors"

        local model_size
        model_size=$(du -h "${sft_model_dir}/adapter_model.safetensors" 2>/dev/null | cut -f1)
        echo "Model size: ${model_size:-N/A}"
    elif [[ -d "$sft_model_dir" ]]; then
        echo "Model path: $sft_model_dir"

        local dir_size
        dir_size=$(du -sh "$sft_model_dir" 2>/dev/null | cut -f1)
        echo "Model size: ${dir_size:-N/A}"
    else
        echo "Model path: $sft_model_dir (not found)"
    fi

    # Training time from stage logs
    if [[ -f "$log_file" ]]; then
        local start_time end_time
        start_time=$(grep -m1 "Start time:" "$log_file" 2>/dev/null | awk '{print $3}')
        end_time=$(grep "End time:" "$log_file" 2>/dev/null | tail -1 | awk '{print $3}')

        if [[ -n "$start_time" && -n "$end_time" ]]; then
            local start_epoch end_epoch duration
            start_epoch=$(date -d "$start_time" +%s 2>/dev/null)
            end_epoch=$(date -d "$end_time" +%s 2>/dev/null)

            if [[ -n "$start_epoch" && -n "$end_epoch" ]]; then
                duration=$((end_epoch - start_epoch))
                echo "Training time: $(format_duration $duration)"
            fi
        fi
    fi
}

# Show GRPO training stage summary
show_grpo_summary() {
    local grpo_output_dir="outputs/grpo"
    local log_file="${LOG_DIR}/${DATE}-grpo.log"

    # Count checkpoints
    local checkpoint_count=0
    if [[ -d "$grpo_output_dir" ]]; then
        checkpoint_count=$(find "$grpo_output_dir" -type d -name "checkpoint-*" 2>/dev/null | wc -l)
    fi
    echo "Checkpoints: $checkpoint_count"

    # Extract final reward from log
    if [[ -f "$log_file" ]]; then
        # Try multiple reward patterns
        local final_reward
        final_reward=$(grep -oP '(?:reward[=:\s]+|"reward":\s*)[-\d.]+' "$log_file" 2>/dev/null | grep -oP '[-\d.]+' | tail -1)

        if [[ -n "$final_reward" ]]; then
            echo "Final reward: $final_reward"
        else
            echo "Final reward: N/A (not found in log)"
        fi
    else
        echo "Final reward: N/A (log file not found)"
    fi

    # Model path
    if [[ -d "${grpo_output_dir}/final" ]]; then
        echo "Model path: ${grpo_output_dir}/final"

        local model_size
        model_size=$(du -sh "${grpo_output_dir}/final" 2>/dev/null | cut -f1)
        echo "Model size: ${model_size:-N/A}"
    else
        echo "Model path: ${grpo_output_dir}/final (not found)"
    fi

    # Training time from stage logs
    if [[ -f "$log_file" ]]; then
        local start_time end_time
        start_time=$(grep -m1 "Start time:" "$log_file" 2>/dev/null | awk '{print $3}')
        end_time=$(grep "End time:" "$log_file" 2>/dev/null | tail -1 | awk '{print $3}')

        if [[ -n "$start_time" && -n "$end_time" ]]; then
            local start_epoch end_epoch duration
            start_epoch=$(date -d "$start_time" +%s 2>/dev/null)
            end_epoch=$(date -d "$end_time" +%s 2>/dev/null)

            if [[ -n "$start_epoch" && -n "$end_epoch" ]]; then
                duration=$((end_epoch - start_epoch))
                echo "Training time: $(format_duration $duration)"
            fi
        fi
    fi
}

# Show final summary for entire pipeline
# Usage: show_final_summary <total_duration_seconds>
show_final_summary() {
    local total_duration="$1"

    local separator="=========================================="
    echo ""
    echo "$separator"
    echo "=== Training Pipeline Complete ==="
    echo "$separator"
    echo ""

    # Show status of each stage
    echo "Stage Status:"

    local stages=("data" "sft" "grpo")
    for stage in "${stages[@]}"; do
        local status="NOT RUN"
        local checkpoint_file=".checkpoints/${stage}.checkpoint"

        if [[ -f "$checkpoint_file" ]]; then
            local checkpoint_status
            checkpoint_status=$(grep "^status=" "$checkpoint_file" | cut -d= -f2)

            case "$checkpoint_status" in
                success)
                    status="COMPLETED"
                    ;;
                failed)
                    status="FAILED"
                    ;;
                running)
                    status="RUNNING"
                    ;;
                *)
                    status="UNKNOWN"
                    ;;
            esac
        fi

        printf "  %-10s %s\n" "${stage}:" "$status"
    done

    echo ""

    # Total duration
    if [[ -n "$total_duration" ]]; then
        echo "Total duration: $(format_duration $total_duration)"
    fi

    # Output paths
    echo ""
    echo "Output Paths:"
    echo "  Data:  outputs/data/"
    echo "  SFT:   outputs/sft/final/"
    echo "  GRPO:  outputs/grpo/final/"

    echo ""
    echo "$separator"
    echo ""
}
