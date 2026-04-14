---
phase: quick-260325-pyp-phase-3-sft-gguf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - outputs/glm5/results.jsonl
  - outputs/sft/sft_train.jsonl
  - outputs/sft/model/config.json
  - outputs/sft/model/model.safetensors
  - outputs/sft/model/model-f16.gguf
  - outputs/sft/model/model-q8_0.gguf
  - outputs/sft/model/model-q4_k_m.gguf
autonomous: true
requirements:
  - ASM-01
  - ASM-02
  - ASM-03
  - TRAIN-01
  - TRAIN-02
  - EXPORT-01
  - EXPORT-02
  - EXPORT-03
user_setup:
  - service: glm5
    why: "Task 1 must regenerate fresh think/solution results instead of reusing old SFT data"
    env_vars:
      - name: GLM_API_KEY
        source: "Zhipu AI / GLM-5 API key"

must_haves:
  truths:
    - "A freshly regenerated outputs/sft/sft_train.jsonl exists and is built from a fresh outputs/glm5/results.jsonl generated in this session"
    - "outputs/sft/model/ is recreated from scratch by a new SFT run and does not reuse the pre-existing model artifacts"
    - "Fresh GGUF exports exist for f16, q8_0, and q4_k_m after the retrain completes"
  artifacts:
    - path: "outputs/glm5/results.jsonl"
      provides: "Fresh GLM-5 generation results for all sampled_5000 inputs"
    - path: "outputs/sft/sft_train.jsonl"
      provides: "Fresh Phase 3 SFT training dataset in messages format"
    - path: "outputs/sft/model/model.safetensors"
      provides: "Freshly retrained merged SFT model"
    - path: "outputs/sft/model/model-f16.gguf"
      provides: "Fresh F16 GGUF export"
    - path: "outputs/sft/model/model-q8_0.gguf"
      provides: "Fresh Q8_0 GGUF export"
    - path: "outputs/sft/model/model-q4_k_m.gguf"
      provides: "Fresh Q4_K_M GGUF export"
  key_links:
    - from: "src/glm5/run_generate.py"
      to: "outputs/glm5/sampled_5000.jsonl"
      via: "fresh GLM-5 batch generation"
      pattern: "sampled_5000\\.jsonl"
    - from: "src/glm5/assembler.py"
      to: "outputs/glm5/results.jsonl"
      via: "assemble fresh results into messages-format SFT data"
      pattern: "results\\.jsonl"
    - from: "docker/sft_train.sh"
      to: "outputs/sft/sft_train.jsonl"
      via: "Docker SFT training run"
      pattern: "sft_train\\.jsonl"
    - from: "docker/convert_gguf.sh"
      to: "outputs/sft/model"
      via: "fresh GGUF conversion from retrained model directory"
      pattern: "model-.*\\.gguf"
---

<objective>
在不新增任何脚本文件的前提下，直接补齐 Phase 3 缺口：重新生成 SFT 数据、删除旧模型后重跑 SFT 训练、再导出新的 GGUF 量化产物。

Purpose: 当前 `outputs/sft/sft_train.jsonl`、`outputs/sft/model/` 和既有 GGUF 都视为旧产物，必须整条链路重建，才能满足 Phase 3 的数据与导出要求。
Output: fresh `outputs/glm5/results.jsonl`, fresh `outputs/sft/sft_train.jsonl`, fresh retrained `outputs/sft/model/*`, fresh `model-f16.gguf` / `model-q8_0.gguf` / `model-q4_k_m.gguf`
</objective>

<execution_context>
@/home/samuel/.codex/get-shit-done/workflows/execute-plan.md
@/home/samuel/.codex/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/03-assembly-export/03-CONTEXT.md
@.planning/phases/03-assembly-export/03-01-SUMMARY.md
@src/glm5/run_generate.py
@src/glm5/client.py
@src/glm5/assembler.py
@docker/sft_train.sh
@docker/convert_gguf.sh
@src/sft/train.py
@config/config.json

<interfaces>
`src/glm5/run_generate.py` consumes `outputs/glm5/sampled_5000.jsonl` and writes `outputs/glm5/results.jsonl`; it requires `GLM_API_KEY`.

`src/glm5/assembler.py` converts fresh `results.jsonl` to `outputs/sft/sft_train.jsonl` in `messages` format expected by `src/sft/train.py`.

`docker/sft_train.sh` will reuse `outputs/sft/sft_train.jsonl` if it exists, so the quick plan must regenerate that file first and must delete `outputs/sft/model/` before training to avoid old model reuse.

`docker/convert_gguf.sh` writes `model-${outtype}.gguf` inside the model directory. Using `--outtype f16`, `--outtype q8_0`, and `--outtype q4_k_m` yields `model-f16.gguf`, `model-q8_0.gguf`, and `model-q4_k_m.gguf`.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Regenerate fresh GLM-5 results and rebuild Phase 3 SFT data</name>
  <files>outputs/glm5/results.jsonl, outputs/sft/sft_train.jsonl</files>
  <action>
    Do not create any new script file. Use only the existing CLI entry points plus inline shell/Python checks.

    1. Hard-delete stale generation/data artifacts before doing anything else:
       - `rm -f outputs/glm5/results.jsonl`
       - `rm -f outputs/sft/sft_train.jsonl`
       This is mandatory because `BatchGenerator` resumes from `results.jsonl`; keeping the old file would silently reuse stale rows.

    2. Verify `GLM_API_KEY` is present, then regenerate fresh results from `outputs/glm5/sampled_5000.jsonl`:
       - `python -m src.glm5.run_generate --input outputs/glm5/sampled_5000.jsonl --output outputs/glm5/results.jsonl`

    3. Assemble the fresh results into the Phase 3 training dataset:
       - `python -m src.glm5.assembler --input outputs/glm5/results.jsonl --output outputs/sft/sft_train.jsonl`

    4. Explicitly avoid the old 100-sample path and legacy workspace artifacts:
       - do not use `outputs/sft/sampled_100.jsonl`
       - do not use `outputs/sft/think_workspace.jsonl`
       - do not use `outputs/sft/train_with_thinking.jsonl`
       - do not add wrapper scripts around the existing commands

    5. Validate that the regenerated dataset is truly Phase 3-ready:
       - `results.jsonl` has exactly 5000 rows and every row has `status == "success"`
       - `sft_train.jsonl` has exactly 5000 rows
       - each SFT row has 3 messages (`system`, `user`, `assistant`)
       - assistant content contains `<start_working_out>`, `<end_working_out>`, `<SOLUTION>`, `</SOLUTION>`
  </action>
  <verify>
    <automated>cd /home/samuel/TSC_CYCLE && python - <<'PY'
import json
from pathlib import Path

results = Path("outputs/glm5/results.jsonl")
sft = Path("outputs/sft/sft_train.jsonl")
assert results.exists(), "missing outputs/glm5/results.jsonl"
assert sft.exists(), "missing outputs/sft/sft_train.jsonl"

with results.open("r", encoding="utf-8") as f:
    result_rows = [json.loads(line) for line in f if line.strip()]
assert len(result_rows) == 5000, f"expected 5000 results, got {len(result_rows)}"
bad = [row.get("status") for row in result_rows if row.get("status") != "success"]
assert not bad, f"non-success statuses found: {bad[:5]}"

with sft.open("r", encoding="utf-8") as f:
    sft_rows = [json.loads(line) for line in f if line.strip()]
assert len(sft_rows) == 5000, f"expected 5000 sft rows, got {len(sft_rows)}"
for row in sft_rows[:20]:
    msgs = row["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"]
    content = msgs[2]["content"]
    assert "<start_working_out>" in content
    assert "<end_working_out>" in content
    assert "<SOLUTION>" in content
    assert "</SOLUTION>" in content
print("fresh results + sft data verified")
PY</automated>
  </verify>
  <done>Fresh `results.jsonl` and fresh `sft_train.jsonl` exist, both at 5000 rows, with no reuse of legacy SFT data artifacts.</done>
</task>

<task type="auto">
  <name>Task 2: Delete the old SFT model directory and retrain from the regenerated dataset</name>
  <files>outputs/sft/model/config.json, outputs/sft/model/model.safetensors</files>
  <action>
    The existing `outputs/sft/model/` contents are explicitly obsolete. Delete them before retraining; do not reuse adapter, merged model, tokenizer, or old GGUF files that happen to be under that directory.

    1. Remove the old model directory completely:
       - `rm -rf outputs/sft/model`

    2. Launch a fresh SFT run with the existing Docker entry point and the already-regenerated `outputs/sft/sft_train.jsonl`:
       - `chmod +x docker/sft_train.sh`
       - `./docker/sft_train.sh`

    3. Do not modify or create scripts. Do not fall back to old 100-sample data generation inside `docker/sft_train.sh`; Task 1 already produced the correct `sft_train.jsonl`, so the Docker script should consume that file directly.

    4. Confirm the retrain actually recreated the model directory from scratch and produced a merged model usable for GGUF conversion:
       - `outputs/sft/model/config.json` exists
       - at least one `*.safetensors` file exists
       - tokenizer assets exist
       - training finishes without format-load failure or NaN/OOM abort
  </action>
  <verify>
    <automated>cd /home/samuel/TSC_CYCLE && python - <<'PY'
from pathlib import Path

model_dir = Path("outputs/sft/model")
assert model_dir.exists(), "model dir missing"
assert (model_dir / "config.json").exists(), "config.json missing"
assert (model_dir / "tokenizer.json").exists() or (model_dir / "tokenizer_config.json").exists(), "tokenizer files missing"
safetensors = list(model_dir.glob("*.safetensors"))
assert safetensors, "no safetensors files found"
print("fresh SFT model verified:", [p.name for p in safetensors])
PY</automated>
  </verify>
  <done>`outputs/sft/model/` has been recreated by a fresh training run and contains a new merged model plus tokenizer/config assets.</done>
</task>

<task type="auto">
  <name>Task 3: Remove stale GGUF files and export fresh f16, q8_0, q4_k_m artifacts</name>
  <files>outputs/sft/model/model-f16.gguf, outputs/sft/model/model-q8_0.gguf, outputs/sft/model/model-q4_k_m.gguf</files>
  <action>
    Export from the freshly retrained model only. Delete both current and legacy-named GGUF files first so stale files cannot masquerade as new output.

    1. Remove stale GGUF artifacts before conversion:
       - `rm -f outputs/sft/model/model-f16.gguf`
       - `rm -f outputs/sft/model/model-q8_0.gguf`
       - `rm -f outputs/sft/model/model-q4_k_m.gguf`
       - `rm -f outputs/sft/model/model-Q8_0.gguf`
       - `rm -f outputs/sft/model/model-Q4_K_M.gguf`

    2. Use the existing Docker converter, no new scripts:
       - `chmod +x docker/convert_gguf.sh`
       - `./docker/convert_gguf.sh --model-path outputs/sft/model --outtype f16`
       - `./docker/convert_gguf.sh --model-path outputs/sft/model --outtype q8_0`
       - `./docker/convert_gguf.sh --model-path outputs/sft/model --outtype q4_k_m`

    3. Keep the lowercase output names above so the generated filenames are deterministic:
       - `model-f16.gguf`
       - `model-q8_0.gguf`
       - `model-q4_k_m.gguf`

    4. Validate existence and rough size sanity after export so Phase 3 closes with deployable artifacts.
  </action>
  <verify>
    <automated>cd /home/samuel/TSC_CYCLE && python - <<'PY'
from pathlib import Path

checks = {
    "model-f16.gguf": 1_000_000_000,
    "model-q8_0.gguf": 1_000_000_000,
    "model-q4_k_m.gguf": 500_000_000,
}
base = Path("outputs/sft/model")
for name, min_bytes in checks.items():
    path = base / name
    assert path.exists(), f"missing {name}"
    size = path.stat().st_size
    assert size > min_bytes, f"{name} too small: {size}"
print("fresh GGUF exports verified")
PY</automated>
  </verify>
  <done>Fresh `model-f16.gguf`, `model-q8_0.gguf`, and `model-q4_k_m.gguf` exist under `outputs/sft/model/` and replaced all stale exports.</done>
</task>

</tasks>

<verification>
The quick plan is complete only if the chain is executed end-to-end in this order:
1. fresh GLM-5 results
2. fresh SFT dataset
3. delete old model and retrain
4. delete old GGUF and re-export

Any reuse of existing `outputs/sft/model/` or existing `outputs/sft/sft_train.jsonl` fails the quick plan.
</verification>

<success_criteria>
- `outputs/glm5/results.jsonl` is regenerated from `outputs/glm5/sampled_5000.jsonl` in the current session with 5000 successful rows
- `outputs/sft/sft_train.jsonl` is regenerated from those fresh results with 5000 Phase 3-compliant SFT rows
- old `outputs/sft/model/` is deleted and replaced by a new SFT training output
- fresh GGUF files exist for `f16`, `q8_0`, and `q4_k_m`
- no new script file is added anywhere in the repo
</success_criteria>

<output>
After completion, create `.planning/quick/260325-pyp-phase-3-sft-gguf/260325-pyp-SUMMARY.md`
</output>
