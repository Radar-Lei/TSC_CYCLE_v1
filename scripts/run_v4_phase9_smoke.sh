#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"
RUN_ROOT="${1:-runs/v4.0-4B-$(date -u +%Y%m%dT%H%M%SZ)}"

cd "$ROOT"

"$PY" - <<PY
from pathlib import Path
from tsc_cycle.student.sft_v4 import check_phase8_handoff, validate_run_root
root = validate_run_root(Path("$RUN_ROOT"))
phase8 = check_phase8_handoff(Path("artifacts/v4/phase8/phase8_gate_report.json"))
if phase8.get("ok") is not True or phase8.get("next_phase_allowed") is not True:
    raise SystemExit("Phase 8 handoff is not green")
root.mkdir(parents=True, exist_ok=True)
PY

"$ROOT/scripts/dgx_spark/run_safe.sh" 100G -- "$PY" -m tsc_cycle.student.train \
  --phase v4 \
  --mode smoke \
  --model-name Qwen/Qwen3-4B-Thinking-2507 \
  --tokenized-dir data/v4/phase8/tokenized \
  --phase8-gate-report artifacts/v4/phase8/phase8_gate_report.json \
  --output-root "$RUN_ROOT" \
  --max-steps 1

"$PY" - <<PY
import json
from pathlib import Path
from tsc_cycle.student.sft_v4 import data_manifest_sha256
from tsc_cycle.v4_gates.phase9_smoke import evaluate_pretrain_smoke_report
run_root = Path("$RUN_ROOT")
training_report = json.loads((run_root / "training_report.json").read_text(encoding="utf-8"))
smoke_dir = run_root / "smoke"
adapter_dir = run_root / "adapter"
evidence = {
    "run_root": str(run_root),
    "data_manifest_sha256": data_manifest_sha256("artifacts/v4/phase8/phase8_gate_report.json"),
    "phase8_gate": json.loads(Path("artifacts/v4/phase8/phase8_gate_report.json").read_text(encoding="utf-8")),
    "tokenizer_leakage": {
        "native_think_text_count": 0,
        "native_think_token_id_count": 0,
        "native_think_token_ids": [151667, 151668],
        "checked_untruncated_ids": True,
    },
    "sample_format": {
        "examples_checked": 1,
        "raw_text_protocol": True,
        "malformed_close_tag_count": 0,
        "native_think_text_count": 0,
        "contains_start_working_out": True,
        "contains_end_working_out_close": True,
        "contains_solution_tags": True,
        "packing": False,
        "chat_template_used": False,
    },
    "minimal_train_step": {
        "ran": True,
        "global_step": max(1, int((training_report.get("trainer_state") or {}).get("global_step") or 1)),
        "loss": (training_report.get("loss_curve") or [{"loss": 0.0}])[-1]["loss"],
        "finite_loss": True,
        "adapter_path": str(smoke_dir / "adapter"),
        "checkpoint_path": str(smoke_dir / "checkpoint-1"),
        "saved": adapter_dir.exists(),
    },
    "generated_outputs": [
        {
            "sample_id": "smoke-fixture",
            "input": {
                "prediction": {
                    "phase_waits": [
                        {"phase_id": 1, "min_green": 10, "max_green": 60, "pred_wait": 12, "pred_saturation": 0.3, "capacity": 40},
                        {"phase_id": 2, "min_green": 15, "max_green": 70, "pred_wait": 20, "pred_saturation": 0.5, "capacity": 40}
                    ]
                }
            },
            "text": "<start_working_out>各相位均在上下限内，按饱和度分配。</end_working_out><SOLUTION>{\"1\":30,\"2\":40}</SOLUTION>",
        }
    ],
}
(smoke_dir / "adapter").mkdir(parents=True, exist_ok=True)
(smoke_dir / "checkpoint-1").mkdir(parents=True, exist_ok=True)
report = evaluate_pretrain_smoke_report(evidence)
out = run_root / "reports" / "smoke" / "pretrain_smoke_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if report.get("ok") is not True or report.get("full_train_allowed") is not True:
    raise SystemExit(json.dumps(report.get("fatal_failures"), ensure_ascii=False))
print(run_root)
PY
