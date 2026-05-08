#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
PHASE_DIR="${ROOT}/data/v3/phase2"
INPUTS_ALL="${PHASE_DIR}/inputs_all.jsonl"
OLD_LABELED="${ROOT}/data/labeled.jsonl"
LABELED_NEW="${PHASE_DIR}/labeled_new.jsonl"
REJECTED_NEW="${PHASE_DIR}/rejected_new.jsonl"
RAW_CACHE="${ROOT}/raw_responses/v3_phase2"
WORKERS="${PHASE2_WORKERS:-10}"
CHUNK_SIZE=500
MIN_ATTEMPTED=7500
MIN_ACCEPTED=6000
MIN_SAME_DIST_ATTEMPTED=5250
MIN_OOD_ATTEMPTED=1500
MIN_TARGETED_ATTEMPTED=750
MODE="${1:-all}"

cd "${ROOT}"

require_clean_old_diff() {
  if ! git diff --quiet -- data/labeled.jsonl; then
    printf 'ERROR: data/labeled.jsonl has uncommitted changes; refusing to continue.\n' >&2
    exit 1
  fi
}

old_sha() {
  "${PYTHON}" - <<'PY'
from pathlib import Path
import hashlib
p = Path("data/labeled.jsonl")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
}

phase2_counts() {
  "${PYTHON}" - <<'PY'
from pathlib import Path
import json
from collections import Counter
paths = [Path("data/v3/phase2/labeled_new.jsonl"), Path("data/v3/phase2/rejected_new.jsonl")]
accepted = rejected = malformed = 0
ids = []
source_attempted = Counter()
source_accepted = Counter()
source_rejected = Counter()
for idx, path in enumerate(paths):
    if not path.exists():
        continue
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if obj.get("sample_id") is not None:
            ids.append(str(obj["sample_id"]))
        source = str(obj.get("source") or (obj.get("input") or {}).get("source") or "unknown")
        source_attempted[source] += 1
        if idx == 0:
            accepted += 1
            source_accepted[source] += 1
        else:
            rejected += 1
            source_rejected[source] += 1
attempted = accepted + rejected
duplicates = sum(n - 1 for n in Counter(ids).values() if n > 1)
reject_rate = rejected / attempted if attempted else 0.0
print(json.dumps({
    "accepted": accepted,
    "rejected": rejected,
    "attempted": attempted,
    "reject_rate": reject_rate,
    "duplicates": duplicates,
    "malformed": malformed,
    "labeled_exists": paths[0].exists(),
    "rejected_exists": paths[1].exists(),
    "source_attempted": dict(source_attempted),
    "source_accepted": dict(source_accepted),
    "source_rejected": dict(source_rejected),
}, sort_keys=True))
PY
}

reservoir_count() {
  "${PYTHON}" - <<'PY'
from pathlib import Path
p = Path("data/v3/phase2/inputs_all.jsonl")
if not p.exists():
    print(0)
else:
    print(sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip()))
PY
}

print_status() {
  local label="$1"
  local counts
  counts="$(phase2_counts)"
  printf '\n[%s]\n' "${label}"
  printf 'root=%s\n' "${ROOT}"
  printf 'phase_dir=%s\n' "${PHASE_DIR}"
  printf 'inputs_all=%s lines=%s\n' "${INPUTS_ALL}" "$(reservoir_count)"
  printf 'labeled_new=%s rejected_new=%s counts=%s\n' "${LABELED_NEW}" "${REJECTED_NEW}" "${counts}"
}

assert_workers_cap() {
  "${PYTHON}" - "${WORKERS}" <<'PY'
import sys
workers = int(sys.argv[1])
if workers > 10:
    raise SystemExit("ERROR: configured workers must be <=10")
if workers < 1:
    raise SystemExit("ERROR: configured workers must be >=1")
PY
}

assert_checkpoint_green() {
  local sha_before="$1"
  local sha_after="$2"
  local counts_json="$3"
  if [[ "${sha_before}" != "${sha_after}" ]]; then
    printf 'ERROR: old baseline SHA changed between checkpoints.\n' >&2
    exit 1
  fi
  "${PYTHON}" - "${counts_json}" <<'PY'
import json
import sys
counts = json.loads(sys.argv[1])
if not counts["labeled_exists"] or not counts["rejected_exists"]:
    raise SystemExit("ERROR: append files are missing after full-run chunk")
if counts["duplicates"] != 0:
    raise SystemExit(f"ERROR: duplicate sample_id count is {counts['duplicates']}")
if counts["malformed"] != 0:
    raise SystemExit(f"ERROR: malformed JSONL line count is {counts['malformed']}")
PY
}

source_coverage_met() {
  local counts_json="$1"
  "${PYTHON}" - "${counts_json}" "${MIN_SAME_DIST_ATTEMPTED}" "${MIN_OOD_ATTEMPTED}" "${MIN_TARGETED_ATTEMPTED}" <<'PY'
import json
import sys
counts = json.loads(sys.argv[1])
minimums = {
    "same_dist": int(sys.argv[2]),
    "ood": int(sys.argv[3]),
    "targeted": int(sys.argv[4]),
}
source_attempted = counts.get("source_attempted") or {}
missing = {
    source: {"attempted": int(source_attempted.get(source, 0)), "minimum": minimum}
    for source, minimum in minimums.items()
    if int(source_attempted.get(source, 0)) < minimum
}
if missing:
    print(json.dumps(missing, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)
PY
}

run_generate() {
  print_status "before generate"
  require_clean_old_diff
  "${ROOT}/scripts/generate_v3_phase2_inputs.sh"
  require_clean_old_diff
  print_status "after generate"
}

run_smoke() {
  print_status "before smoke"
  require_clean_old_diff
  "${ROOT}/scripts/run_v3_phase2_label_smoke.sh"
  require_clean_old_diff
  print_status "after smoke"
}

run_merge() {
  print_status "before merge"
  require_clean_old_diff
  "${ROOT}/scripts/run_v3_phase2_merge.sh"
  require_clean_old_diff
  print_status "after merge"
}

run_full_chunks() {
  assert_workers_cap
  local total_inputs
  total_inputs="$(reservoir_count)"
  if [[ "${total_inputs}" -le 0 ]]; then
    printf 'ERROR: %s is missing or empty; run generate first.\n' "${INPUTS_ALL}" >&2
    exit 1
  fi

  while true; do
    local counts_before attempted_before accepted_before rejected_before sha_before
    counts_before="$(phase2_counts)"
    attempted_before="$("${PYTHON}" - "${counts_before}" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["attempted"])
PY
)"
    accepted_before="$("${PYTHON}" - "${counts_before}" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["accepted"])
PY
)"
    rejected_before="$("${PYTHON}" - "${counts_before}" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["rejected"])
PY
)"

    if [[ "${attempted_before}" -ge "${MIN_ATTEMPTED}" && "${accepted_before}" -ge "${MIN_ACCEPTED}" ]]; then
      if source_coverage_met "${counts_before}"; then
        printf 'Full labeling checkpoint target met: attempted=%s accepted=%s rejected=%s.\n' "${attempted_before}" "${accepted_before}" "${rejected_before}"
        break
      fi
      printf 'Full labeling checkpoint still needs source coverage; counts=%s\n' "${counts_before}"
    fi

    if [[ "${attempted_before}" -ge "${total_inputs}" ]]; then
      if [[ "${accepted_before}" -lt "${MIN_ACCEPTED}" ]]; then
        printf 'USER DECISION REQUIRED: reservoir exhausted with attempted=%s accepted=%s rejected=%s; accepted < %s.\n' "${attempted_before}" "${accepted_before}" "${rejected_before}" "${MIN_ACCEPTED}" >&2
        exit 3
      fi
      if ! source_coverage_met "${counts_before}"; then
        printf 'ERROR: reservoir exhausted without required source coverage; counts=%s\n' "${counts_before}" >&2
        exit 1
      fi
      printf 'Reservoir exhausted after sufficient accepted labels and source coverage: attempted=%s accepted=%s rejected=%s.\n' "${attempted_before}" "${accepted_before}" "${rejected_before}"
      break
    fi

    sha_before="$(old_sha)"
    printf '\n[FULL CHECKPOINT BEFORE CHUNK]\n'
    printf 'old_sha_before=%s\n' "${sha_before}"
    printf 'accepted=%s rejected=%s attempted=%s workers=%s chunk_size=%s\n' "${accepted_before}" "${rejected_before}" "${attempted_before}" "${WORKERS}" "${CHUNK_SIZE}"

    "${PYTHON}" -m tsc_cycle.teacher.labeler \
      --input-files data/v3/phase2/inputs_all.jsonl \
      --exclude-labeled data/labeled.jsonl \
      --labeled data/v3/phase2/labeled_new.jsonl \
      --rejected data/v3/phase2/rejected_new.jsonl \
      --cache-dir raw_responses/v3_phase2 \
      --workers "${WORKERS}" \
      --limit "${CHUNK_SIZE}" \
      --model gpt-5.5 \
      --effort high \
      --cost-out data/v3/phase2/teacher_cost.full.latest.json \
      --reject-stats data/v3/phase2/teacher_reject_stats.full.latest.json

    local sha_after counts_after
    sha_after="$(old_sha)"
    counts_after="$(phase2_counts)"
    assert_checkpoint_green "${sha_before}" "${sha_after}" "${counts_after}"
    printf '\n[FULL CHECKPOINT AFTER CHUNK]\n'
    printf 'old_sha_after=%s counts=%s\n' "${sha_after}" "${counts_after}"
  done

  local final_counts
  final_counts="$(phase2_counts)"
  printf '\n[FULL LABELING TOTALS]\n%s\n' "${final_counts}"
}

run_full() {
  print_status "before full"
  require_clean_old_diff
  run_full_chunks
  require_clean_old_diff
  run_merge
  require_clean_old_diff
  print_status "after full"
}

case "${MODE}" in
  generate)
    run_generate
    ;;
  smoke)
    run_smoke
    ;;
  full)
    run_full
    ;;
  merge)
    run_merge
    ;;
  all)
    run_generate
    run_smoke
    printf '\nBLOCKING: Smoke completed. Review smoke outputs, then rerun this wrapper with mode `full` after approval.\n'
    printf 'Command after approval: %s/scripts/run_v3_phase2_all.sh full\n' "${ROOT}"
    ;;
  *)
    printf 'Usage: %s [generate|smoke|full|merge|all]\n' "$0" >&2
    exit 2
    ;;
esac

require_clean_old_diff
