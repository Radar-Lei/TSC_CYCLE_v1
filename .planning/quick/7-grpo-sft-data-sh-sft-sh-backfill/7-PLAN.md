---
phase: quick-7
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/grpo/ (DELETE entire directory)
  - src/scripts/train_grpo.py (DELETE)
  - docker/grpo.sh (DELETE)
  - Qwen3_(4B)_GRPO.ipynb (DELETE)
  - config/config.json
  - docker/run.sh
autonomous: true
must_haves:
  truths:
    - "No GRPO-related files exist in the repository"
    - "config.json contains only SFT training config, simulation config, and correct paths"
    - "docker/run.sh orchestrates data -> sft pipeline only"
    - "SFT pipeline (data.sh, sft.sh, backfill_thinking.py) remains fully intact"
  artifacts:
    - path: "config/config.json"
      provides: "Clean config without GRPO sections"
      contains: "training.sft, simulation, paths (no grpo_output, no rewards)"
    - path: "docker/run.sh"
      provides: "Simplified pipeline orchestrator"
      contains: "data -> sft pipeline stages only"
  key_links:
    - from: "docker/run.sh"
      to: "docker/data.sh, docker/sft.sh"
      via: "bash script calls"
      pattern: "bash.*data\\.sh|bash.*sft\\.sh"
---

<objective>
Remove all GRPO-related code from the repository and simplify the pipeline to data generation -> SFT training only.

Purpose: The project no longer uses GRPO training. Clean up dead code to reduce confusion and maintenance burden.
Output: A streamlined codebase with only the SFT pipeline.
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@config/config.json
@docker/run.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delete all GRPO files and directories</name>
  <files>
    src/grpo/
    src/scripts/train_grpo.py
    docker/grpo.sh
    Qwen3_(4B)_GRPO.ipynb
  </files>
  <action>
Delete the following using rm commands:

1. `rm -rf src/grpo/` — entire GRPO module (data_loader.py, format_reward.py, reward_combiner.py, simulation_reward.py, sumo_evaluator.py, trainer.py, __init__.py, __pycache__)
2. `rm src/scripts/train_grpo.py` — GRPO training entry point
3. `rm docker/grpo.sh` — GRPO Docker launch script
4. `rm "Qwen3_(4B)_GRPO.ipynb"` — GRPO Jupyter notebook

Do NOT touch:
- src/sft/ (SFT trainer)
- src/data_generator/ (data generation)
- src/scripts/generate_training_data.py, train_sft.py, backfill_thinking.py, process_phases.py
- docker/data.sh, docker/sft.sh, docker/Dockerfile
- sumo_simulation/
- unsloth_compiled_cache/
  </action>
  <verify>
Run: `ls src/grpo/ 2>&1` should return "No such file or directory"
Run: `ls src/scripts/train_grpo.py docker/grpo.sh "Qwen3_(4B)_GRPO.ipynb" 2>&1` should all return "No such file"
Run: `ls src/sft/trainer.py src/scripts/train_sft.py docker/data.sh docker/sft.sh` should all exist
  </verify>
  <done>All GRPO files deleted. SFT pipeline files untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Clean config.json and simplify docker/run.sh</name>
  <files>
    config/config.json
    docker/run.sh
  </files>
  <action>
**config/config.json** — Remove three sections, keep the rest:

Remove:
- `training.grpo` object (lines 18-46) — GRPO training hyperparameters
- `rewards` object (lines 54-57) — GRPO reward weights
- `paths.grpo_output` key (line 62) — GRPO output path

Keep:
- `training.sft` — SFT training config
- `simulation` — used by generate_training_data.py
- `paths.data_dir`, `paths.sft_data_dir`, `paths.sft_output`, `paths.environments_dir`

Result should be:
```json
{
  "training": {
    "sft": { ... existing sft config unchanged ... }
  },
  "simulation": { ... existing simulation config unchanged ... },
  "paths": {
    "data_dir": "data/training",
    "sft_data_dir": "outputs/sft",
    "sft_output": "outputs/sft/model",
    "environments_dir": "sumo_simulation/environments"
  }
}
```

**docker/run.sh** — Simplify to data -> sft pipeline only:

1. Update header comments: pipeline is now `data -> sft` only, no GRPO references
2. Remove `direct` stage concept (was data -> grpo skipping SFT)
3. Default STAGE should be `all` (data -> sft)
4. Supported stages: `all` (data -> sft), `data` (data only), `sft` (sft only)
5. Remove the GRPO stage block (lines 70-74)
6. Update usage message to reflect new stages
7. Update banner text: remove "GRPO" from title, use "SFT 交通信号优化 - 训练流程"
8. Update output directory listing: remove GRPO output line, always show SFT output
9. Stage numbering: data is 阶段 1/2, sft is 阶段 2/2
  </action>
  <verify>
Run: `python3 -c "import json; c=json.load(open('config/config.json')); assert 'grpo' not in c['training']; assert 'rewards' not in c; assert 'grpo_output' not in c['paths']; assert 'sft' in c['training']; assert 'simulation' in c; print('config OK')"` should print "config OK"
Run: `grep -i grpo docker/run.sh` should return no matches (exit code 1)
Run: `bash -n docker/run.sh` should pass (valid bash syntax)
  </verify>
  <done>config.json contains only SFT/simulation/paths config. docker/run.sh orchestrates data -> sft only with no GRPO references.</done>
</task>

</tasks>

<verification>
1. No GRPO files exist: `find . -path ./node_modules -prune -o -name "*grpo*" -print -o -name "*GRPO*" -print` returns nothing (except planning docs)
2. Config is valid JSON with correct structure
3. docker/run.sh is syntactically valid bash
4. SFT pipeline files are all intact: src/sft/, src/scripts/train_sft.py, docker/data.sh, docker/sft.sh
</verification>

<success_criteria>
- Zero GRPO files remain in src/, docker/, or project root
- config.json parses as valid JSON with only training.sft, simulation, and paths (without grpo_output)
- docker/run.sh has no GRPO references and orchestrates data -> sft flow
- All SFT pipeline files exist and are unchanged
</success_criteria>

<output>
After completion, create `.planning/quick/7-grpo-sft-data-sh-sft-sh-backfill/7-SUMMARY.md`
</output>
