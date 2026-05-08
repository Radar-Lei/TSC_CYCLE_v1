# Phase 2: 数据扩量到 10K（教师只标新增 7K） - Research

**Researched:** 2026-05-08 [VERIFIED: project memory currentDate]
**Domain:** 离线合成数据扩量 / GPT-5.5 high 教师并发标注 / append-only JSONL 数据治理 [VERIFIED: .planning/ROADMAP.md]
**Confidence:** HIGH for existing v1.0 pipeline reuse; MEDIUM for final reject rate until 50-sample + 500-sample smoke runs complete [VERIFIED: local code + v1 artifacts; ASSUMED: reject-rate projection]

## User Constraints (from CONTEXT.md)

### Locked Decisions

（CONTEXT.md 未提供 `## Decisions` 独立小节；以下为 Phase Boundary 与 Success Criteria 的锁定约束。） [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]

在不动 v1.0 `data/labeled.jsonl` 字节的前提下，扩展合成输入分布、用 GPT-5.5 high 并发标注新增 ≥7K 输入，过硬约束 lint 后与 v1.0 合并得到 ≥9000 valid 训练集。 [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]

Success criteria from ROADMAP: [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]
1. 合成输入分布扩展到三类（同分布密集填充 / OOD 边界 / v1.0 高 MAE 与 lint reject targeted），生成 ≥7K 新输入且与 v1.0 现有 3K 不重叠（去重后）。 [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]
2. GPT-5.5 high + reasoning_effort=high 标注完成；并发 ≤10 worker；JSONL append 进度持久化；中断可断点续跑且不重复调用。 [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]
3. 教师输出过硬约束 lint（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），lint 失败样本丢弃不重生成；最终合并集 ≥9000 valid samples。 [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]
4. v1.0 `data/labeled.jsonl` git diff clean（read-only mount 引用，字节级不变）；新增样本写入隔离路径。 [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, requirements, and codebase conventions to guide decisions. [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)

None — discuss phase skipped. [VERIFIED: .planning/phases/02-10k-7k/02-CONTEXT.md]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATAGEN-01 | 合成输入生成器扩展分布到三类：(a) 同分布密集填充 (b) OOD / 边界（min_green<15s, max_green>120s, 极端饱和度等）(c) v1.0 高 MAE / lint reject targeted 案例 | 现有 `sample_inputs.py` 已支持同分布与 7 类 OOD；需新增 targeted sampler，从 `runs/20260507T032419Z/eval/per_sample.jsonl` 的 lint fail / high-MAE 样本派生邻域扰动。 [VERIFIED: sample_inputs.py + local v1 eval artifact] |
| DATAGEN-02 | 生成 ≥7K 新输入（去重后），与 v1.0 现有 3K 不重叠 | `hashing.sample_id()` 使用 canonical JSON 的 SHA-256；本地 v1.0 `data/labeled.jsonl` 为 3000 行且 3000 unique IDs；现有 `data/inputs.jsonl` + `data/ood_inputs.jsonl` 与 `data/labeled.jsonl` overlap=3000，说明 Phase 2 必须写新隔离路径并显式排除旧 IDs。 [VERIFIED: hashing.py + local dataset probe] |
| DATAGEN-03 | GPT-5.5 high + reasoning_effort="high"，并发 ≤10 worker，指数退避，复用 `EvoProgTSC/client.py` 既有重试/降级逻辑 | 本仓 `teacher/client.py` 已使用 Responses API `reasoning={"effort": ...}`、处理 `RateLimitError` 与指数退避；`teacher/labeler.py` 已用 `ThreadPoolExecutor(max_workers=args.workers)`，默认 workers=10。 [VERIFIED: teacher/client.py + teacher/labeler.py; CITED: /openai/openai-python Context7] |
| DATAGEN-04 | 教师输出过硬约束 lint（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位）；lint 失败样本丢弃不重生成 | `constraint_lint.validate()` 已验证 dict、phase key 集合、phase order、整数、min/max；`teacher/labeler.py` 当前 lint 失败写 rejected，不重新提交该样本。 [VERIFIED: constraint_lint.py + teacher/labeler.py + tests/test_constraint_lint.py] |
| DATAGEN-05 | 进度持久化 JSONL append；支持断点续跑（不重复调用 GPT-5.5） | `teacher/labeler.py` 从 labeled/rejected 读取 done sample IDs，完成后 append+flush；`teacher/client.py` 对 successful response 使用 prompt hash cache。 [VERIFIED: teacher/labeler.py + teacher/client.py] |
| DATAGEN-06 | v3.0 训练集 = v1.0 valid `labeled.jsonl` (read-only) ∪ 新增 lint pass samples，目标 ≥9000 valid samples | v1.0 `data/labeled.jsonl` 当前 3000 行、3000 success；Phase 2 至少需要 ≥6000 新 valid 才能达到 ≥9000 merged valid。 [VERIFIED: local dataset probe + .planning/REQUIREMENTS.md] |
| DATAGEN-07 | v1.0 `data/labeled.jsonl` 内容字节级不变（git diff clean，仅以 read-only mount 方式被引用） | 本地 `data/labeled.jsonl` 当前 SHA-256 为 `2214301555f22640e542234abcd9c5f0e3f6982df08c894124af45367ad30809`；`git diff -- data/labeled.jsonl` 当前无输出；Phase 2 必须将新增 labels 写入 `data/v3/phase2/` 隔离路径。 [VERIFIED: local SHA/git probe] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- 所有用户可见回复必须使用简体中文。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Git commit message 不得包含 `Co-Authored-By`。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 本机是 DGX Spark，暂时不能使用 vLLM。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- DGX Spark 训练必须遵循 `/dgx-spark-training` 约束：不使用 upstream flash-attn cu12，使用 SDPA，加入 swap/OOM 防护，复用已知良好 venv。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 教师 API 并发 ≤10 worker；遇 RPM/TPM 触发指数退避。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 教师输出必须通过硬约束 lint 后才能进训练集。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 自定义思考标签必须保持普通多 sub-token 文本，不能使用原生 `<think>` 语义路径。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md + tests/test_prompt_builder.py]
- 不要直接读取或发送整个 PDF，应按页拆分；本阶段不涉及 PDF。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- GSD 工作流要求不要在无 GSD 入口的情况下做直接代码改动；本任务是 `/gsd-plan-phase` 派生研究，允许写 Phase research artifact。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md + gsd-sdk init.phase-op]

## Summary

Phase 2 应按“**冻结 v1.0 数据、隔离新增数据、最终显式合并**”来规划，而不是复用 v1.0 的 `teacher.labeler` 默认路径直接 append 到 `data/labeled.jsonl`。 [VERIFIED: ROADMAP success criteria + teacher/labeler.py defaults] 当前代码已有可复用的 v1.0 基础：同分布/OOD 采样器、内容寻址 sample_id、Responses API 教师 client、10 worker labeler、硬约束 lint、append+flush 续跑机制。 [VERIFIED: sample_inputs.py + hashing.py + teacher/client.py + teacher/labeler.py + constraint_lint.py]

关键增量是三处：第一，新增 targeted sampler，从 v1.0 eval 的 lint fail / high-MAE 样本派生邻域扰动，并确保新 sample_id 与 v1.0 训练/评测样本不重叠。 [VERIFIED: runs/20260507T032419Z/eval/per_sample.jsonl probe; ASSUMED: 邻域扰动是最佳 targeted 策略] 第二，把 labeler 改成支持 `--input-files` / `--exclude-labeled` / `--cache-dir` / `--max-workers <=10` / `--labeled-new`，从而只标新增样本并把结果写入隔离路径。 [VERIFIED: current labeler CLI lacks targeted/cache/exclude args] 第三，生成 `merge_report` 与 manifest，证明 v1.0 file hash 未变、新增 valid 数、合并 valid 数、reject 统计与三源覆盖均满足 DATAGEN-01..07。 [VERIFIED: requirements]

**Primary recommendation:** 生成一个 7,500 条去重候选 reservoir（70% same-dist / 20% OOD / 10% targeted），按固定顺序标注至少 7,000 条；如果 `new_valid < 6,000`，继续使用预生成 reserve 直到 7,500 条耗尽；lint 失败只丢弃、不为失败样本重生成；最终将 v1.0 3000 valid 与新增 valid 合并到 `data/v3/phase2/labeled_merged.jsonl`，并保持 `data/labeled.jsonl` SHA-256 不变。 [VERIFIED: ≥9000 valid math + requirements; ASSUMED: 7,500 reservoir buffer accepted]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| 三源候选输入生成 | Offline data generation (`tsc_cycle/sample_inputs.py`) | `distribution_fit.py`, v1 eval artifacts | 输入分布与模型训练/评测解耦；同分布来自 prior，OOD 来自 spec，targeted 来自历史失败。 [VERIFIED: sample_inputs.py + distribution_fit.py + v1 eval artifact] |
| 新旧样本去重 | Data identity layer (`tsc_cycle/hashing.py`) | Candidate generator | `sample_id` 是 canonical input JSON 的 SHA-256，适合作为跨文件去重主键。 [VERIFIED: hashing.py + tests/test_hashing.py] |
| 教师标注并发 | External API client + labeler (`tsc_cycle/teacher/*`) | OpenAI Responses API | API 调用、rate limit、cache、parse、usage 统计属于 teacher integration 边界。 [VERIFIED: teacher/client.py + teacher/labeler.py; CITED: OpenAI Python SDK README] |
| 硬约束 lint | Pure Python validator (`tsc_cycle/constraint_lint.py`) | Teacher labeler and eval | 相位覆盖、相位顺序、整数、min/max 是数据准入门，不应散落在 sampler 或 prompt 中。 [VERIFIED: constraint_lint.py] |
| Append-only 进度持久化 | Labeler output layer | Prompt cache | 断点续跑由 labeled/rejected JSONL 与 raw response cache 共同保证。 [VERIFIED: teacher/labeler.py + teacher/client.py] |
| v1.0 read-only 保护 | Data governance / manifest layer | Git diff + file hash | DATAGEN-07 是阶段成功门，必须由 manifest 记录 before/after hash 与 git diff clean。 [VERIFIED: requirements + local SHA probe] |
| 合并集构建 | Offline dataset assembly | Phase 3 retokenize | Phase 2 只产 raw JSONL 合并集，Phase 3 再 split/tokenize。 [VERIFIED: ROADMAP Phase 2/3 boundary] |

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python | 3.12.3 in `/home/samuel/TSC_CYCLE/.venv` | Datagen / labeler runtime | Project venv is the target runtime used by Phase 1 gates. [VERIFIED: local venv probe] |
| OpenAI Python SDK | 2.34.0 installed | Responses API teacher calls | `teacher/client.py` already uses `OpenAI().responses.create()` and `reasoning={"effort": ...}`; SDK docs expose Responses API and `RateLimitError`. [VERIFIED: local venv + teacher/client.py; CITED: OpenAI Python SDK README; VERIFIED: Context7 /openai/openai-python] |
| scipy | 1.17.1 installed | KS tests for distribution report | Existing `scripts/dist_check.py` imports `scipy.stats.ks_2samp`. [VERIFIED: local venv + scripts/dist_check.py] |
| numpy | 2.3.5 installed | Numeric sampling/statistics support | Already present in project venv; useful for report statistics if needed. [VERIFIED: local venv] |
| pytest | 9.0.3 installed | Unit/integration tests | `pyproject.toml` configures pytest with `testpaths=["tests"]` and `addopts="-q"`. [VERIFIED: local venv + pyproject.toml] |
| pydantic | 2.13.4 installed | Optional schema-typed manifests | Present in venv; use for manifest/report schemas if planner wants typed models. [VERIFIED: local venv] |
| jsonschema | 4.26.0 installed | Optional schema validation | Declared in project deps and installed in project venv; useful for strict manifest tests. [VERIFIED: local venv + pyproject.toml] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `concurrent.futures` | Python stdlib | `ThreadPoolExecutor(max_workers<=10)` | Use for teacher parallelism; do not add another concurrency framework. [VERIFIED: teacher/labeler.py] |
| `hashlib` / `json` | Python stdlib | canonical IDs, prompt hashes, JSONL IO | Already used in `hashing.py` and labeler. [VERIFIED: hashing.py + teacher/labeler.py] |
| `tenacity` | 9.1.4 installed | Optional retries | Not required because `teacher/client.py` already implements retry/backoff; do not introduce unless refactoring retry policy. [VERIFIED: local venv + teacher/client.py] |
| `pyarrow` | 24.0.0 installed | Later Phase 3 tokenized parquet | Phase 2 should not tokenize, but Phase 3 consumes merged JSONL. [VERIFIED: local venv + ROADMAP Phase 3] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `ThreadPoolExecutor` labeler | OpenAI Batch API | Batch can reduce cost but introduces long latency and does not fit immediate lint/drop/resume loop; current requirements explicitly ask ≤10 worker concurrent labeling. [VERIFIED: requirements; ASSUMED: Batch latency/cost tradeoff] |
| Existing `constraint_lint.validate()` | New validator or JSON Schema only | JSON Schema cannot express all phase-order/min-max checks as cleanly as the existing project validator; reuse avoids dual truth. [VERIFIED: constraint_lint.py] |
| In-place append to `data/labeled.jsonl` | Isolated `data/v3/phase2/labeled_new.jsonl` + merged output | In-place append violates DATAGEN-07; isolated paths preserve v1.0 bytes and auditability. [VERIFIED: requirements + teacher/labeler.py defaults] |
| Label exactly 7,000 new candidates | Pre-generated 7,500 candidate reservoir | Exact 7,000 succeeds only if reject rate ≤14.3%; a fixed reserve gives room while preserving “drop failures, do not regenerate failed samples.” [VERIFIED: ≥9000 valid math; ASSUMED: reserve acceptable] |

**Installation:** No new install should be needed on the happy path. [VERIFIED: project venv probe]

```bash
source /home/samuel/TSC_CYCLE/.venv/bin/activate
python -m pytest -q
```

**Version verification performed:** `/home/samuel/TSC_CYCLE/.venv/bin/python` reports Python 3.12.3; installed package versions include openai 2.34.0, scipy 1.17.1, numpy 2.3.5, pytest 9.0.3, pydantic 2.13.4, jsonschema 4.26.0, tenacity 9.1.4, pyarrow 24.0.0, transformers 5.8.0, datasets 4.8.5. [VERIFIED: local venv probe]

## Architecture Patterns

### System Architecture Diagram

```text
Frozen v1.0 data (read-only)
  data/labeled.jsonl  --sha256 gate-->  old_valid_ids + old_valid_records
        |                                                |
        |                                                v
        |                                     old_id exclusion set
        |                                                |
        v                                                v
  v1 eval artifacts ------------------> targeted seed selector
  runs/20260507T032419Z/eval/per_sample.jsonl             |
                                                           v
reality.log prior / dist_prior.json ---> same-dist sampler + OOD sampler + targeted sampler
                                                           |
                                                           v
                                      candidate reservoir (>=7,500; source tagged)
                                                           |
                                           dedupe against old_valid_ids + self
                                                           |
                                                           v
                                      data/v3/phase2/{inputs_*.jsonl, manifest}
                                                           |
                                                           v
                                      teacher labeler (GPT-5.5 high, <=10 workers)
                                      |  - prompt_builder raw protocol
                                      |  - response cache in isolated cache dir
                                      |  - append+flush labeled_new/rejected_new
                                      |  - constraint_lint gate
                                      v
                    data/v3/phase2/labeled_new.jsonl + rejected_new.jsonl
                                      |
                         if new_valid >= 6000 and old hash unchanged
                                      v
                    data/v3/phase2/labeled_merged.jsonl (>=9000 valid)
                                      |
                                      v
                    merge_report.json + datagen_report.md + before/after hashes
                                      |
                                      v
                         Phase 3 Dataset Rebuild consumes merged JSONL
```

### Recommended Project Structure

```text
tsc_cycle/
├── sample_inputs.py              # extend with v3 reservoir + targeted sampler [VERIFIED: file exists]
├── hashing.py                    # unchanged canonical sample_id [VERIFIED: file exists]
├── constraint_lint.py            # unchanged hard gate [VERIFIED: file exists]
├── manifest.py                   # extend with datagen/merge manifest helpers [VERIFIED: file exists]
└── teacher/
    ├── client.py                 # mostly unchanged; expose cache_dir via labeler [VERIFIED: file exists]
    └── labeler.py                # add isolated input/output/cache/exclude args [VERIFIED: file exists]

data/
└── v3/
    └── phase2/
        ├── inputs_same_dist.jsonl
        ├── inputs_ood.jsonl
        ├── inputs_targeted.jsonl
        ├── inputs_all.jsonl
        ├── labeled_new.jsonl
        ├── rejected_new.jsonl
        ├── labeled_merged.jsonl
        ├── datagen_manifest.json
        ├── merge_report.json
        └── datagen_report.md

raw_responses/
└── v3_phase2/                    # recommended isolated prompt cache [ASSUMED]
```

### Pattern 1: Frozen baseline + isolated delta

**What:** Treat `data/labeled.jsonl` as immutable baseline; read it only for old IDs and merge input; write all new artifacts under `data/v3/phase2/`. [VERIFIED: DATAGEN-07 + local file probe]

**When to use:** Any Phase 2 task that handles labels or generated inputs. [VERIFIED: success criteria]

**Example:**
```python
# Source: project pattern recommendation [ASSUMED]
old_bytes = Path("data/labeled.jsonl").read_bytes()
old_sha = hashlib.sha256(old_bytes).hexdigest()
# ... write only data/v3/phase2/labeled_new.jsonl ...
assert hashlib.sha256(Path("data/labeled.jsonl").read_bytes()).hexdigest() == old_sha
```

### Pattern 2: Pre-generated reservoir, no failed-sample regeneration

**What:** Generate a fixed reservoir of new candidates before API calls; label in deterministic order; if rejects reduce `new_valid` below 6000, continue into pre-generated reserve; never create a replacement “because sample X failed lint.” [VERIFIED: lint failure drop requirement; ASSUMED: reserve strategy]

**When to use:** Teacher labeling stage where final merged valid count must be ≥9000. [VERIFIED: DATAGEN-06]

**Recommended ratios for 7,500 reservoir:** same-dist 5,250; OOD 1,500; targeted 750. [ASSUMED]

### Pattern 3: Targeted neighbor sampling from v1 failures

**What:** Select seed sample IDs from v1 per-sample eval where any backend has `lint_ok=false` or `mae>10`, then perturb numeric fields while preserving schema and recomputing sample_id. [VERIFIED: v1 eval artifact has 1800 rows; local probe found 8 lint-fail rows / 4 lint-fail IDs / 232 mae>10 rows / 104 mae>10 IDs; ASSUMED: mae>10 threshold]

**When to use:** DATAGEN-01 targeted class. [VERIFIED: requirements]

**Example:**
```python
# Source: derived from local v1 per_sample.jsonl format [VERIFIED]
if rec.get("lint_ok") is False or (rec.get("mae") or 0) > 10.0:
    seed_ids.add(rec["sample_id"])
```

### Pattern 4: Resume-safe append with explicit done set

**What:** On startup, read `labeled_new.jsonl` + `rejected_new.jsonl` to skip already attempted new IDs; append one JSON line per completed sample and flush immediately. [VERIFIED: teacher/labeler.py]

**When to use:** All full labeling runs and smoke runs. [VERIFIED: DATAGEN-05]

**Critical adaptation:** Do not use `data/labeled.jsonl` as the `--labeled` output path; pass old v1 data only as `--exclude-labeled`/dedupe source. [VERIFIED: teacher/labeler.py defaults would otherwise append to v1]

### Anti-Patterns to Avoid

- **Appending new labels to `data/labeled.jsonl`:** This violates DATAGEN-07 and makes byte-level v1 comparison fail. [VERIFIED: requirements]
- **Using existing `data/inputs.jsonl` / `data/ood_inputs.jsonl` as Phase 2 output:** Local probe shows those 3000 input IDs overlap 100% with current `data/labeled.jsonl`, so they are v1 inputs, not new Phase 2 candidates. [VERIFIED: local overlap probe]
- **Retrying lint-failed samples with a modified prompt:** Requirement says lint failures are discarded, not regenerated; retrying failed semantics biases training toward overexplained edge cases. [VERIFIED: requirements; ASSUMED: bias rationale]
- **Changing `prompt_builder.USER_TEMPLATE` during Phase 2:** Prompt text is part of prompt hash; changing it invalidates old cache and changes teacher behavior mid-milestone. [VERIFIED: teacher/client.py prompt_hash includes prompt; ASSUMED: behavior drift risk]
- **Letting workers exceed 10 via CLI:** Current labeler accepts any integer; Phase 2 should clamp/fail if `--workers > 10`. [VERIFIED: teacher/labeler.py + CLAUDE.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API retry / backoff | New retry loop or tenacity wrapper | Existing `TeacherClient.call()` | It already handles `RateLimitError`, timeout/connection/API errors, parse errors, cache writes, and usage capture. [VERIFIED: teacher/client.py] |
| Hard-constraint lint | New JSON Schema-only validator | `constraint_lint.validate()` | Existing validator covers dict shape, phase set, phase order, integer coercion, min/max. [VERIFIED: constraint_lint.py + tests/test_constraint_lint.py] |
| Sample identity | UUIDs or line numbers | `hashing.sample_id(input_obj)` | Stable SHA-256 over canonical JSON enables dedupe across reruns and old/new files. [VERIFIED: hashing.py + tests/test_hashing.py] |
| Distribution checks | Hand-written CDF tests | `scripts/dist_check.py` + `scipy.stats.ks_2samp` | Existing script already reports same-dist and OOD KS behavior. [VERIFIED: scripts/dist_check.py] |
| Manifest hash logic | Ad-hoc shell `sha256sum` only | Extend `manifest.py` + Python hash checks | `manifest.py` already anchors git SHA/config hash and is the right project location for dataset provenance. [VERIFIED: manifest.py] |
| Prompt protocol parse | New parser | `prompt_builder.parse_assistant_output()` | Existing parser enforces current tags and rejects legacy `</end_working_out>`. [VERIFIED: prompt_builder.py + tests/test_prompt_builder.py] |

**Key insight:** The hard part is data governance, not API plumbing; reusing project primitives prevents the new 7K from corrupting the v1 baseline. [ASSUMED]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `data/labeled.jsonl` exists with 3000 lines, 3000 unique sample IDs, 3000 successful records, SHA-256 `2214301555f22640e542234abcd9c5f0e3f6982df08c894124af45367ad30809`. [VERIFIED: local probe] | Treat as read-only input; record before/after SHA; never pass as labeler output. [VERIFIED: DATAGEN-07] |
| Stored data | `data/inputs.jsonl` has 2700 lines and `data/ood_inputs.jsonl` has 300 lines; their IDs overlap current `data/labeled.jsonl` by 3000. [VERIFIED: local probe] | Do not reuse as Phase 2 “new” inputs; generate isolated v3 inputs and exclude old IDs. [VERIFIED: DATAGEN-02] |
| Stored data | `data/rejected.jsonl` exists with 1 line. [VERIFIED: local probe] | Do not mix v1 reject file into v3 new reject output; use `data/v3/phase2/rejected_new.jsonl`. [ASSUMED] |
| Stored data | `raw_responses/` exists with 3003 JSON files; first 50 sampled files contain legacy `</end_working_out>` and not current `<end_working_out>`. [VERIFIED: local cache probe] | Use isolated `raw_responses/v3_phase2/` cache for new prompts; do not rely on old cache for current protocol. [VERIFIED: prompt_builder.py rejects legacy tag; ASSUMED: isolated cache path] |
| Stored data | `runs/20260507T032419Z/eval/per_sample.jsonl` exists with 1800 rows and can seed targeted sampling. [VERIFIED: local probe] | Read only; extract lint-fail / high-MAE seed IDs; ensure targeted output IDs do not overlap source IDs. [VERIFIED: DATAGEN-01] |
| Live service config | OpenAI API is accessed through environment variables read by `TeacherClient`; current shell has no `OPENAI_API_KEY`. [VERIFIED: teacher/client.py + environment probe] | Planner must include preflight requiring `OPENAI_API_KEY`; optionally record `OPENAI_BASE_URL` without printing secrets. [VERIFIED: teacher/client.py] |
| OS-registered state | No Phase 2 systemd/cron service was found in project scope. [VERIFIED: project file search] | None. [VERIFIED: search] |
| Secrets/env vars | `OPENAI_API_KEY` is required; `OPENAI_BASE_URL` is optional; `GPT5_5_INPUT_PER_M` / `GPT5_5_OUTPUT_PER_M` affect cost estimates. [VERIFIED: teacher/client.py + teacher/labeler.py] | Do not write secrets to logs/manifests; record only boolean presence and base URL host if needed. [ASSUMED] |
| Build artifacts | No new binary build is required; tokenized parquet belongs to Phase 3, not Phase 2. [VERIFIED: ROADMAP Phase boundary] | Do not run dataset tokenization in Phase 2. [VERIFIED: ROADMAP] |

## Common Pitfalls

### Pitfall 1: Accidentally mutating v1.0 `data/labeled.jsonl`
**What goes wrong:** Current `teacher/labeler.py` defaults `--labeled=data/labeled.jsonl`, so invoking it without new args will append Phase 2 records to the protected v1.0 file. [VERIFIED: teacher/labeler.py]
**Why it happens:** v1.0 pipeline was designed for first dataset creation, not frozen-baseline delta labeling. [VERIFIED: v1 audit + labeler defaults]
**How to avoid:** Add a Phase 2 wrapper/CLI args that fail if output path equals `data/labeled.jsonl`; write new labels to `data/v3/phase2/labeled_new.jsonl`. [ASSUMED]
**Warning signs:** `git status --short -- data/labeled.jsonl` shows modification or before/after SHA differs. [VERIFIED: git probe pattern]

### Pitfall 2: Counting old inputs as new inputs
**What goes wrong:** Reusing existing `data/inputs.jsonl` and `data/ood_inputs.jsonl` appears to satisfy 3000 candidate count but all IDs already exist in v1.0 labels. [VERIFIED: local overlap probe]
**Why it happens:** Existing file names are generic and not versioned. [VERIFIED: project file list]
**How to avoid:** Always write Phase 2 candidates under `data/v3/phase2/` and compute `overlap_with_v1_labeled == 0` as a hard gate. [ASSUMED]
**Warning signs:** Any overlap count >0 in `datagen_manifest.json`. [ASSUMED]

### Pitfall 3: Exact 7K candidate plan fails ≥9000 valid gate
**What goes wrong:** With exactly 7000 new candidates, any reject rate above 14.285% leaves fewer than 6000 new valid samples and final merged count below 9000. [VERIFIED: arithmetic from DATAGEN-06]
**Why it happens:** Requirements require lint failures to be dropped, not regenerated. [VERIFIED: DATAGEN-04]
**How to avoid:** Pre-generate a fixed reserve reservoir, label at least 7000 and continue into reserve if valid count is below 6000; never generate replacements after seeing failures. [ASSUMED]
**Warning signs:** `teacher_reject_stats.json` shows reject rate approaching 10% before 500-sample checkpoint. [ASSUMED]

### Pitfall 4: Targeted samples leak v1 eval examples into training
**What goes wrong:** If targeted sampler copies v1 failed sample inputs directly, the new training set can contain the exact eval sample ID, invalidating cross-milestone evaluation. [VERIFIED: v1 eval artifact exists; ASSUMED: leak impact]
**Why it happens:** v1 failed examples are tempting seeds but should not be reused verbatim. [ASSUMED]
**How to avoid:** Perturb fields and recompute sample_id; assert targeted IDs have zero overlap with v1 `data/labeled.jsonl`, v1 `inputs/ood_inputs`, and v1 eval per_sample IDs. [VERIFIED: hashing.py; ASSUMED: overlap set list]
**Warning signs:** `targeted_seed_overlap_count > 0` in manifest. [ASSUMED]

### Pitfall 5: Legacy raw response cache collides with current parser expectations
**What goes wrong:** Existing raw response cache contains legacy `</end_working_out>` text, while current parser rejects that legacy tag. [VERIFIED: local cache probe + prompt_builder.py]
**Why it happens:** Phase 7 protocol migration happened after v1.0 labeling; cache content is historical. [VERIFIED: v2 Phase 7 research + local cache probe]
**How to avoid:** Do not reparse old raw cache for v1 baseline; use `data/labeled.jsonl` records as frozen valid labels and use a new cache namespace for Phase 2. [ASSUMED]
**Warning signs:** New labeler run reports parse errors on cached responses before making API calls. [ASSUMED]

### Pitfall 6: `RateLimitError` retry sleeps all workers at once
**What goes wrong:** Current `TeacherClient.call()` sleeps inside a worker on rate limit; at 10 workers, synchronized retries can cause bursty traffic. [VERIFIED: teacher/client.py]
**Why it happens:** Backoff is per-thread and has no global token bucket. [VERIFIED: teacher/client.py]
**How to avoid:** Add jitter or reduce workers to 5 when rate limits appear; keep ≤10 hard cap. [ASSUMED]
**Warning signs:** Many records show `ratelimit:` errors or long elapsed times with low throughput. [VERIFIED: teacher/client.py records errors]

## Code Examples

### Isolated labeler invocation
```bash
# Source: recommended Phase 2 invocation pattern [ASSUMED]
/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.teacher.labeler \
  --input-files data/v3/phase2/inputs_all.jsonl \
  --exclude-labeled data/labeled.jsonl \
  --labeled data/v3/phase2/labeled_new.jsonl \
  --rejected data/v3/phase2/rejected_new.jsonl \
  --cache-dir raw_responses/v3_phase2 \
  --workers 10 \
  --model gpt-5.5 \
  --effort high
```

### Merge gate invariant
```python
# Source: DATAGEN-06/07 planning pattern [ASSUMED]
old = read_jsonl(Path("data/labeled.jsonl"))
new = read_jsonl(Path("data/v3/phase2/labeled_new.jsonl"))
assert len(old) == 3000
assert sum(r["result"]["success"] for r in new) >= 6000
assert not ({r["sample_id"] for r in old} & {r["sample_id"] for r in new})
write_jsonl(Path("data/v3/phase2/labeled_merged.jsonl"), old + new_valid)
```

### Targeted seed selection
```python
# Source: local v1 eval per_sample format [VERIFIED]
def load_targeted_seed_ids(per_sample_path: Path, mae_threshold: float = 10.0) -> set[str]:
    seed_ids: set[str] = set()
    for line in per_sample_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("lint_ok") is False or (rec.get("mae") or 0.0) > mae_threshold:
            seed_ids.add(rec["sample_id"])
    return seed_ids
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.0 two-source data: same-dist + OOD | v3.0 three-source data: same-dist dense + OOD boundary + targeted high-error/lint-reject neighborhood | Phase 2 v3.0 requirement | Improves coverage of failure modes while preserving v1.0 baseline bytes. [VERIFIED: DATAGEN-01] |
| Generic `data/labeled.jsonl` as mutable label output | Frozen `data/labeled.jsonl` + isolated `data/v3/phase2/labeled_new.jsonl` + merged output | Phase 2 v3.0 requirement | Enables byte-level DATAGEN-07 proof. [VERIFIED: DATAGEN-07] |
| Default labeler path labels all `data/inputs.jsonl` + `data/ood_inputs.jsonl` | Explicit input-file list and exclude-labeled set | Phase 2 planning recommendation | Prevents duplicate calls and old-data mutation. [VERIFIED: labeler defaults; ASSUMED: new CLI design] |
| Old raw response cache in root `raw_responses/` | New cache namespace `raw_responses/v3_phase2/` | Phase 2 planning recommendation | Avoids legacy tag cache parse failures and improves auditability. [VERIFIED: local cache probe; ASSUMED: namespace design] |

**Deprecated/outdated:**
- `teacher/labeler.py` default output to `data/labeled.jsonl` is outdated for Phase 2 and must not be used without override. [VERIFIED: teacher/labeler.py + DATAGEN-07]
- Current `scripts/run_pipeline.sh` label-count gate `<2700` is v1.0-specific and not suitable for Phase 2 ≥9000 valid gate. [VERIFIED: scripts/run_pipeline.sh]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 7,500 pre-generated reservoir is acceptable under “教师只标新增 ≥7K” because failures are not regenerated and only new samples are labeled. | Summary / Pattern 2 | If user interprets title as exactly 7000 API calls, planner must use exact 7000 and accept reject-rate risk. |
| A2 | 70/20/10 source ratio is the right starting point. | Pattern 2 | Too much targeted data could overfit failure neighborhoods; too little OOD could under-improve boundary behavior. |
| A3 | MAE > 10 is a better targeted seed threshold than MAE > 5. | Pattern 3 | If too strict, targeted seeds may under-cover moderate errors; if too loose, targeted set becomes generic OOD. |
| A4 | Isolated `raw_responses/v3_phase2/` cache is preferred over reusing root cache. | Runtime State / State of Art | More API calls if identical current-protocol prompts already exist elsewhere, but avoids legacy parser cache issues. |
| A5 | Adding labeler CLI args is preferable to writing a separate Phase 2 labeler. | Architecture Patterns | If retrofitting labeler becomes messy, a thin wrapper may be safer. |

## Open Questions (RESOLVED)

1. **RESOLVED — Phase 2 uses a pre-declared 7,500-candidate reservoir, not an exact 7,000-candidate ceiling.**
   - Decision: Generate 7,500 new candidate inputs up front with the planned 5,250 same-dist / 1,500 OOD / 750 targeted source split. Full labeling must attempt at least 7,000 new inputs and may continue into the remaining reserve only when needed to reach `new_valid >= 6000`. If the 7,500 reserve is exhausted before `new_valid >= 6000`, stop for a user decision rather than generating replacements. [RESOLVED: checker fix_hint + DATAGEN-02/04/06]

2. **RESOLVED — Targeted seeds are `lint_ok is False ∪ mae > 10.0`.**
   - Decision: Use v1 eval rows from `runs/20260507T032419Z/eval/per_sample.jsonl` where `lint_ok is False` or `mae > 10.0`, then perturb numeric fields and recompute `sample_id`; do not use the broader MAE>5 threshold in Phase 2. [RESOLVED: checker fix_hint + local v1 eval probe]

3. **RESOLVED — Keep `reasoning_tokens_min=100` unless the 50-sample smoke exposes a blocker.**
   - Decision: Full-run labeler configuration keeps the existing `reasoning_tokens_min=100` behavior. The 50-sample smoke may surface evidence that this blocks otherwise valid labels; if so, stop for a user decision before changing the threshold. [RESOLVED: checker fix_hint + teacher/client.py]


## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv` | All Phase 2 Python commands | ✓ | Python 3.12.3 | None needed. [VERIFIED: local venv probe] |
| OpenAI Python SDK | Teacher API | ✓ | 2.34.0 | None needed. [VERIFIED: local venv probe] |
| `OPENAI_API_KEY` | Teacher API execution | ✗ in current shell | — | No functional fallback; planner must require export before smoke/full run. [VERIFIED: environment probe + teacher/client.py] |
| `OPENAI_BASE_URL` | Optional proxy/endpoint override | Not required by code | — | Use OpenAI default if unset. [VERIFIED: teacher/client.py] |
| scipy | Distribution report | ✓ | 1.17.1 | Could skip KS report, but DATAGEN-01 evidence would be weaker. [VERIFIED: local venv + scripts/dist_check.py] |
| pytest | Validation | ✓ | 9.0.3 | None. [VERIFIED: local venv + pyproject.toml] |
| `runs/20260507T032419Z/eval/per_sample.jsonl` | Targeted sampler | ✓ | 1800 rows | If absent, targeted class blocks and user decision required. [VERIFIED: local probe] |
| `data/dist_prior.json` | Same-dist/OOD sampler | ✓ | existing JSON | Recompute from `reality.log` if needed. [VERIFIED: project file list + distribution_fit.py] |
| `raw_responses/` | Historical cache reference | ✓ | 3003 JSON files | Use isolated v3 cache; old cache not required. [VERIFIED: local probe] |

**Missing dependencies with no fallback:**
- `OPENAI_API_KEY` is required before any teacher smoke/full run. [VERIFIED: teacher/client.py + environment probe]

**Missing dependencies with fallback:**
- None for code/test work; API execution is the only runtime blocker. [VERIFIED: environment probe]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 [VERIFIED: local venv probe] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` with `testpaths=["tests"]`, `addopts="-q"` [VERIFIED: pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_hashing.py tests/test_constraint_lint.py tests/test_prompt_builder.py` [VERIFIED: files exist] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` [VERIFIED: pyproject.toml] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DATAGEN-01 | Three-source reservoir has same-dist/OOD/targeted counts and source tags | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_three_source_reservoir_counts` | ❌ Wave 0 |
| DATAGEN-01 | Targeted seeds come from lint-fail ∪ high-MAE v1 eval rows | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_targeted_seed_provenance` | ❌ Wave 0 |
| DATAGEN-02 | New candidate sample IDs have zero overlap with v1 `data/labeled.jsonl` | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_no_overlap_with_v1_labeled` | ❌ Wave 0 |
| DATAGEN-03 | Labeler fails if workers >10 and calls Responses API with high effort | unit with mock client | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_workers_capped_and_effort_high` | ❌ Wave 0 |
| DATAGEN-04 | Lint-failed teacher response goes to rejected_new and is not retried | unit with mock client | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_lint_failure_dropped_not_retried` | ❌ Wave 0 |
| DATAGEN-05 | Resume skips IDs already in labeled_new/rejected_new | unit with mock client | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_resume_skips_done_ids` | ❌ Wave 0 |
| DATAGEN-06 | Merge output count ≥9000 and all new records lint-pass | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_merge.py::test_merged_valid_count_gate` | ❌ Wave 0 |
| DATAGEN-07 | `data/labeled.jsonl` SHA unchanged after Phase 2 commands | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_merge.py::test_v1_labeled_sha_unchanged` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** quick pytest command plus any newly added focused test file. [ASSUMED]
- **Per wave merge:** full pytest suite. [ASSUMED]
- **Before full API run:** 50-sample smoke using isolated output and `--limit 50`; require low reject rate and no v1 SHA change. [ASSUMED]
- **During full API run:** checkpoint every 500 attempted samples; verify workers≤10, append files growing, reject rate under threshold, and old SHA unchanged. [ASSUMED]
- **Phase gate:** full suite + manifest gate: `old_sha_before == old_sha_after`, `new_valid >= 6000`, `merged_valid >= 9000`, `overlap_old_new == 0`. [VERIFIED: DATAGEN requirements; ASSUMED: exact gate script]

### Wave 0 Gaps

- [ ] `tests/test_v3_datagen_inputs.py` — covers DATAGEN-01/02 targeted provenance, ratios, dedupe. [ASSUMED]
- [ ] `tests/test_v3_labeler.py` — covers DATAGEN-03/04/05 with mock `TeacherClient`. [ASSUMED]
- [ ] `tests/test_v3_datagen_merge.py` — covers DATAGEN-06/07 merge and SHA invariants. [ASSUMED]
- [ ] `tests/conftest.py` fixtures for mini v1 labeled, mini per_sample eval, fake teacher outputs. [ASSUMED]
- [ ] CLI support in `teacher/labeler.py` for input files, exclude-labeled, isolated cache dir, and worker cap. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | `OPENAI_API_KEY` via environment variable only; never write key to JSONL, logs, manifests, or git. [VERIFIED: teacher/client.py; ASSUMED: logging discipline] |
| V3 Session Management | no | No web sessions or browser state in this offline pipeline. [VERIFIED: phase scope] |
| V4 Access Control | yes | Protect v1.0 baseline from unauthorized writes by path guard + SHA gate. [VERIFIED: DATAGEN-07] |
| V5 Input Validation | yes | Use `constraint_lint.validate()` and JSON parse guards before accepting teacher outputs. [VERIFIED: constraint_lint.py + prompt_builder.py] |
| V6 Cryptography | no | No cryptographic protocol; SHA-256 is used only for integrity/deduplication, not security. [VERIFIED: hashing.py] |
| V8 Data Protection | yes | Avoid leaking API keys and keep v1.0 labels immutable; raw responses may contain model text but no secrets by design. [VERIFIED: teacher/client.py; ASSUMED: prompts contain no secrets] |

### Known Threat Patterns for teacher API + offline data pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage into logs/manifests | Information Disclosure | Never serialize environment variables; log only `api_key_present: true/false`. [ASSUMED] |
| Budget denial-of-wallet through repeated cache misses | Denial of Service | 50-sample smoke, prompt freeze, isolated cache, cost report, and manual stop threshold. [VERIFIED: labeler cost output; ASSUMED: stop threshold] |
| Baseline data tampering | Tampering | Before/after SHA-256, git diff check, output path guard. [VERIFIED: DATAGEN-07] |
| Malformed teacher JSON | Tampering | `parse_assistant_output` catches parse errors; `constraint_lint` rejects bad types and phase mismatches. [VERIFIED: prompt_builder.py + constraint_lint.py] |
| Concurrency burst causes rate limit loop | Denial of Service | Cap at 10 workers; reduce to 5 with jitter if rate limits appear. [VERIFIED: CLAUDE.md + labeler.py; ASSUMED: jitter addition] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/02-10k-7k/02-CONTEXT.md` — Phase boundary, discretion, success criteria. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — DATAGEN-01..07 requirements. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 2 goal and success criteria. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — v3.0 decision history and v1.0 baseline metrics. [VERIFIED]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/sample_inputs.py` — existing same-dist + OOD sampler and constants. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/teacher/client.py` — Responses API, reasoning effort, cache, retry, rate-limit handling. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/teacher/labeler.py` — current labeler CLI, append/resume, worker pool, lint path. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py` and `tests/test_constraint_lint.py` — hard-constraint validator behavior. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/hashing.py` and `tests/test_hashing.py` — canonical JSON + SHA sample ID. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` and `tests/test_prompt_builder.py` — current protocol tags and parser behavior. [VERIFIED]
- Local probes of `data/labeled.jsonl`, `data/inputs.jsonl`, `data/ood_inputs.jsonl`, `raw_responses/`, and `runs/20260507T032419Z/eval/per_sample.jsonl`. [VERIFIED]
- Context7 `/openai/openai-python` — `responses.create(reasoning={"effort": ...})` effort values and retry configuration snippets. [VERIFIED]
- OpenAI Python SDK README — Responses API usage, `RateLimitError`, default retries, and `response.output_text`. [CITED: https://raw.githubusercontent.com/openai/openai-python/main/README.md]

### Secondary (MEDIUM confidence)
- OpenAI Responses API reference search result — documents `reasoning` object and `reasoning.effort`. [CITED: https://platform.openai.com/docs/api-reference/responses]
- OpenAI reasoning guide search result — explains reasoning tokens and effort cost/latency tradeoff. [CITED: https://platform.openai.com/docs/guides/reasoning]
- OpenAI rate-limits guide search result — recommends pacing and exponential backoff. [CITED: https://platform.openai.com/docs/guides/rate-limits]
- OpenAI error-codes guide search result — documents HTTP 429 and Python SDK `RateLimitError`. [CITED: https://platform.openai.com/docs/guides/error-codes]

### Tertiary (LOW confidence)
- Exact reject-rate projection for 7K+ new OOD/targeted labels; must be validated by smoke/checkpoints. [ASSUMED]
- Best targeted ratio and MAE threshold; recommended but needs empirical confirmation from generated report. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against project venv, codebase, Context7/OpenAI SDK docs. [VERIFIED]
- Architecture: HIGH — v1.0 pipeline exists and Phase 2 boundaries are explicit; isolated delta pattern directly satisfies DATAGEN-07. [VERIFIED]
- Pitfalls: HIGH for file mutation/dedupe/cache issues due to local probes; MEDIUM for reject-rate and targeted-ratio risks. [VERIFIED + ASSUMED]
- API execution readiness: MEDIUM — code and SDK are present, but `OPENAI_API_KEY` is not set in current shell. [VERIFIED]

**Research date:** 2026-05-08 [VERIFIED: project memory]
**Valid until:** 2026-05-15 for OpenAI API operational details; 2026-06-08 for local code/data layout if no major refactor occurs. [ASSUMED]
