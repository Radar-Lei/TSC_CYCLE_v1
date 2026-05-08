Phase 2 artifact contract for v3 10K/7K data expansion

This file is an artifact contract for operators and downstream automation.
It is not the training dataset and it does not contain secrets.

data/labeled.jsonl is frozen. Phase 2 tools may read it for old IDs, old records,
and SHA evidence, but must not append to it or rewrite it.

Phase 3 consumes only data/v3/phase2/labeled_merged.jsonl.

Required Phase 2 files:
- inputs_same_dist.jsonl
- inputs_ood.jsonl
- inputs_targeted.jsonl
- inputs_all.jsonl
- datagen_manifest.json
- labeled_new.jsonl
- rejected_new.jsonl
- labeled_merged.jsonl
- merge_report.json

Artifact meanings:
- inputs_same_dist.jsonl contains same-distribution dense-fill candidate inputs.
- inputs_ood.jsonl contains OOD and boundary candidate inputs.
- inputs_targeted.jsonl contains v1.0 high-MAE or lint-reject targeted neighbor inputs.
- inputs_all.jsonl is the deterministic candidate reservoir used by the labeler.
- datagen_manifest.json records source counts, sample-ID dedupe evidence, old-overlap evidence, and old baseline SHA evidence.
- labeled_new.jsonl is append-only accepted GPT-5.5 high output after hard-constraint lint.
- rejected_new.jsonl is append-only rejected output for API, parse, or hard-constraint failures.
- labeled_merged.jsonl is the old valid set plus accepted new labels, written only by the merge gate.
- merge_report.json is the final gate report for DATAGEN-01 through DATAGEN-07.

lint-failed samples are discarded, not regenerated. The fixed candidate reservoir is
used in deterministic order; rejected samples are not replaced with newly generated
samples after seeing failures.

Raw API responses live under raw_responses/v3_phase2/ without secrets. Prompts and
model outputs may be stored there for audit/cache purposes, but environment variable
values and API keys must never be written to those files.

Full labeling is checkpointed every 500 attempted samples. Each checkpoint must
include baseline SHA evidence, accepted/rejected counts, attempted count, worker cap
evidence, duplicate-ID evidence, and reject-rate evidence. The worker cap must remain
at 10 or lower.

The canonical operational wrapper is scripts/run_v3_phase2_all.sh. In all mode it
runs generate and smoke only, then stops for approval before paid full labeling. In
full mode it labels in 500-attempt chunks, checks the frozen baseline, and runs the
merge/report gate after full-label targets are met.
