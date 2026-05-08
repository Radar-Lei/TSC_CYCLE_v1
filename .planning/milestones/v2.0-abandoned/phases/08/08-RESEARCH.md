# Phase 8: 10K 混合数据扩容与教师标注 - Research

**Researched:** 2026-05-08
**Domain:** 合成数据生成 + GPT-5.5 high 教师并发标注 + 数据集 split / dataset card
**Confidence:** HIGH

## Summary

Phase 8 在 v1.0 已落地的 3000 样本闭环之上，把规模扩到 10K，并把样本来源从「同分布 + OOD」二元混合扩成「同分布 + OOD/边界 + v1.0 错误/高 MAE targeted」三元混合。

v1.0 的所有关键代码已经存在并通过验证：`tsc_cycle/sample_inputs.py`（同分布 + 7 维 OOD 采样器）、`tsc_cycle/teacher/labeler.py`（10 worker 并发 + 断点续跑 + 硬约束 lint + 拒绝桶）、`tsc_cycle/teacher/client.py`（Responses API + reasoning_effort=high + 内容寻址缓存 + reasoning_tokens 阈值闸）、`tsc_cycle/constraint_lint.py`（min/max/整数/相位顺序硬约束）、`tsc_cycle/student/dataset.py`（80/10/10 三 split + token 长度统计 + dataset card）。**Phase 8 是工程扩容而非新建栈**——重点在于：(1) 新增 v1.0 失败样本回放/邻域采样器，(2) 把数据源/比例做成显式可记录的 manifest，(3) 增强 dataset 报告以满足 DATA-02 的"三类比例 + v1.0 差异"要求，(4) split metadata 落盘支持 DATA-03 的可复现性。

**Primary recommendation:** 延续现有 `sample_inputs.py` + `teacher/labeler.py` + `student/dataset.py` 三段式 pipeline；**新增** `tsc_cycle/sample_inputs.py::sample_targeted()` 函数（从 `runs/20260507T032419Z/eval/per_sample.jsonl` 读取 v1.0 失败样本作为种子，应用扰动生成邻域样本），**新增** `data/dataset_manifest.json`（记录三源比例、随机种子、输入版本、标注版本），**扩展** `dataset.py` 输出 `data/dataset_report.md`（DATA-02 的字段分布 + 边界覆盖 + v1.0 对比表）。raw_responses cache（已 3003 个文件）天然支持续跑，扩到 10K 时旧 7000 个新 prompt 直接 miss 缓存进入 API，旧 3000 hit 缓存零成本复用。

## User Constraints (from CONTEXT.md)

### Locked Decisions

所有实现选择由 Planner/Executor 决定，约束遵循：
- 使用 GPT-5.5 high 教师，`reasoning_effort="high"`，并发 ≤ 10 worker
- 教师输出必须通过硬约束 lint（min/max/整数/相位覆盖）才能进入训练集
- 标注流程必须支持断点续跑（JSONL append）
- train/val/OOD split metadata 需记录随机种子、输入版本和标注版本
- 协议格式遵循 Phase 7 已锁定的 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`

### Claude's Discretion

- 三类样本的具体比例（建议 7:2:1，见下文 §"Don't Hand-Roll"）
- v1.0 错误样本的"邻域扰动"具体生成策略（建议 ±10% 字段扰动 + ID 重哈希，见下文）
- 10K 中 train/val/OOD 的具体切分（建议沿用 80/10/10，但 OOD 单独 sticky）
- dataset_report.md 的字段集合（建议覆盖 §"DATA-02 Report Schema"）

### Deferred Ideas

None — discuss phase skipped。

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | 系统能生成 10K 候选输入，覆盖同分布、OOD/边界、v1.0 错误/高 MAE targeted | §Architecture Pattern 1（三源采样器）+ §"v1.0 失败样本回放"+ §File Change Map（`sample_inputs.py` 扩展 + `dataset_manifest.json`） |
| DATA-02 | 数据集构建报告记录三类比例、字段分布、边界覆盖和与 v1.0 差异 | §"DATA-02 Report Schema"+ §File Change Map（`dataset_report.md` 输出） |
| DATA-03 | GPT-5.5 high 标注通过硬约束 lint 后形成可复现 train/val/OOD split，metadata 记录随机种子/输入版本/标注版本 | §"Existing teacher pipeline 复用"+ §"Split metadata 字段"+ §File Change Map（`student/dataset.py` 加 manifest 输出） |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 三源候选输入采样 | offline data generation (`tsc_cycle/sample_inputs.py`) | reality.log prior (`distribution_fit.py`) | 同分布走 dist_prior，OOD 走 ood_spec，targeted 读 v1.0 eval 输出 |
| 教师 API 并发标注 | external API client (`tsc_cycle/teacher/client.py`) | content-addressed cache (`raw_responses/`) | 已就位，扩到 10K 自动续跑 |
| 硬约束 lint | pure python validator (`tsc_cycle/constraint_lint.py`) | — | 已就位，无需改 |
| 数据 split + tokenize | offline build (`tsc_cycle/student/dataset.py`) | parquet IO (pyarrow) | sample_id-hash 桶决定性切分 |
| 数据报告生成 | offline report (`scripts/dist_check.py` + dataset.py 末段) | — | 扩展为 dataset_report.md（DATA-02 要求） |
| Manifest 持久化 | offline (新增 `tsc_cycle/manifest.py`) | hashing.py | 已有 `tsc_cycle/manifest.py` 占位文件，需要扩展 |

## Standard Stack

### Core (已锁定，全部已在 venv 中)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | >=1.50.0 | Responses API + reasoning_effort | `teacher/client.py` 已用 `client.responses.create(reasoning={"effort": "high"})` |
| pyarrow | >=15.0.0 | parquet IO for tokenized splits | `student/dataset.py:21` 已用 |
| scipy | >=1.13.0 | KS 检验（同分布 / OOD 验证） | `scripts/dist_check.py:13` 已用 |
| numpy | >=1.26.0 | 数值采样 | dist_prior 数值字段 |
| transformers | >=4.56.2 | tokenizer for length stats | `student/dataset.py` 已用 |
| jsonschema | >=4.20.0 | 教师输出 schema 校验（如选用） | 已声明在 pyproject deps |
| pytest | >=8.0.0 | 单测 | `tests/` 已有 3 个文件 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| concurrent.futures | stdlib | ThreadPoolExecutor(max_workers=10) | 已在 `labeler.py:25` 用 |
| hashlib | stdlib | sample_id = sha256(canonical_input) | 已在 `hashing.py` 用 |
| Counter | stdlib | reject_kinds 分布、ood_dim 计数 | 已在 `labeler.py`/`dataset.py` 用 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ThreadPoolExecutor(10) | OpenAI Batch API | Batch 便宜约 50%，但 24h 延迟，无法做"lint 失败立即丢弃 + 看 reject_rate"的快速循环；10K @ 10 worker 同步 ≈ 2-4h，可控 |
| sample_id-hash 桶切分 | sklearn train_test_split | 哈希桶可在不同运行间稳定（DATA-03 可复现性的核心）；sklearn 需要把 seed 同时锚定 |
| 自写 v1.0 错误读取 | datasets.load_dataset | per_sample.jsonl 是 1800 行 JSONL，stdlib 直接读，引 datasets 库无收益 |

**Installation verification:** 不需要新增依赖。所有库已在 `pyproject.toml` 声明，版本与 v1.0 一致。

## Architecture Patterns

### System Architecture Diagram

```
┌─ inputs ───────────────────────────────────────────────┐
│ data/dist_prior.json    (reality.log → KS-pass prior)  │
│ data/ood_spec.md        (7 OOD dimensions)             │
│ runs/20260507T032419Z/eval/per_sample.jsonl  (v1.0)    │
└──────────┬────────────────┬──────────────────┬─────────┘
           │                │                  │
           ▼                ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
   │ sample_id_   │  │ sample_ood   │  │ sample_targeted  │
   │ (in-dist)    │  │ (mutate ≥1   │  │ (v1.0 失败 +     │
   │ ~7000        │  │  OOD dim)    │  │  邻域扰动) ~1000 │
   │              │  │ ~2000        │  │                  │
   └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
          └─────────────────┼──────────────────┘
                            ▼
              ┌────────────────────────────┐
              │ data/inputs.jsonl          │  ← split_hint=id
              │ data/ood_inputs.jsonl      │  ← split_hint=ood
              │ data/targeted_inputs.jsonl │  ← split_hint=id (新)
              │ data/dataset_manifest.json │  (三源比例 + 种子 + 版本)
              └────────────┬───────────────┘
                           ▼
                   ┌───────────────────┐
                   │ teacher.labeler   │
                   │  - 10 worker      │
                   │  - prompt cache   │
                   │  - reasoning gate │
                   │  - lint + reject  │
                   └────────┬──────────┘
                            ▼
              ┌────────────────────────────┐
              │ data/labeled.jsonl         │
              │ data/rejected.jsonl        │
              │ runs/{ts}/teacher_cost.json│
              │ runs/{ts}/teacher_reject_  │
              │           stats.json       │
              └────────────┬───────────────┘
                           ▼
                   ┌───────────────────┐
                   │ student.dataset   │
                   │  - tokenize       │
                   │  - sample_id-hash │
                   │    bucket split   │
                   │  - dataset_card   │
                   │  - dataset_report │  ← 新增
                   │  - split_manifest │  ← 新增
                   └────────┬──────────┘
                            ▼
              ┌────────────────────────────┐
              │ data/tokenized/{train,     │
              │   val_id, val_ood}/        │
              │   data.parquet             │
              │ data/dataset_card.md       │
              │ data/dataset_report.md     │  ← DATA-02
              │ data/split_manifest.json   │  ← DATA-03
              └────────────────────────────┘
```

### Recommended Project Structure（以现状为准）

```
tsc_cycle/
├── sample_inputs.py          # 已存在；扩展 sample_targeted()
├── distribution_fit.py       # 已存在；不动
├── constraint_lint.py        # 已存在；不动
├── prompt_builder.py         # 已存在；不动（Phase 7 已迁移协议）
├── hashing.py                # 已存在；不动
├── manifest.py               # 已存在（占位）；扩展为 build_dataset_manifest()
├── teacher/
│   ├── client.py             # 已存在；不动
│   └── labeler.py            # 已存在；可能加 --targeted-inputs 参数
└── student/
    └── dataset.py            # 已存在；扩展 dataset_report + split_manifest

data/
├── dist_prior.json                          # 已存在
├── inputs.jsonl                             # 同分布（扩到 ~7000）
├── ood_inputs.jsonl                         # OOD（扩到 ~2000）
├── targeted_inputs.jsonl                    # 新增 ~1000
├── dataset_manifest.json                    # 新增
├── labeled.jsonl                            # append（v1.0 3000 cache hit + 7000 new）
├── rejected.jsonl                           # append
├── dataset_card.md                          # 已扩展
├── dataset_report.md                        # 新增（DATA-02）
└── split_manifest.json                      # 新增（DATA-03）

scripts/
└── dist_check.py             # 已存在；扩展支持 targeted 维度
```

### Pattern 1: 三源混合采样

**What:** 每个候选输入有唯一 `source ∈ {id, ood, targeted}`；总数 10K，按比例采样并记录 manifest。

**When to use:** DATA-01 强制要求"覆盖同分布、OOD/边界、v1.0 错误/高 MAE targeted"。

**Recommended proportions:**
- `id`：≈ 7000（70%）— 主体训练信号；同分布充足后，模型在熟悉分布上稳定
- `ood`：≈ 2000（20%）— OOD 泛化的核心；v1.0 仅 300 OOD 训练样本，扩展 6.7×
- `targeted`：≈ 1000（10%）— v1.0 失败修补；从 v1.0 OOD 失败 + 高 MAE 案例中重采样

理由：v1.0 的 OOD lint=99.3% / q4_K_M=98.7% 来自 300 OOD 训练样本；扩到 2000 OOD 训练样本可让 q4_K_M 在更多 OOD 维度组合上看到教师答案。targeted 1000 是"针对性补丁"，避免过大（>20% 会让 v1.0 失败模式主导分布）。

**Example:**
```python
# Source: tsc_cycle/sample_inputs.py (扩展)
def sample_targeted(
    rng: random.Random,
    prior: dict,
    eval_path: Path,            # runs/20260507T032419Z/eval/per_sample.jsonl
    n_targeted: int = 1000,
    perturbation_ratio: float = 0.1,
) -> list[dict]:
    """从 v1.0 eval 失败案例 + 高 MAE 案例做种子，应用 ±10% 字段扰动。

    选种条件:
      - lint_ok=False  (硬约束失败 — 最高优先)
      - mae > 5.0      (数值显著偏离教师 — 次优先)
      - 任一 backend (hf_bf16, gguf_bf16, gguf_q4_k_m) 触发即可
    """
    seeds = []
    for line in eval_path.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("lint_ok") is False or (rec.get("mae") or 0) > 5.0:
            seeds.append(rec["sample_id"])
    seeds = list(set(seeds))  # 去重，多 backend 同一 sample_id 算一次
    # 反查每个 seed 对应的 input（从 data/labeled.jsonl[idx].input）
    # 然后对每个种子生成 ~ceil(n_targeted/len(seeds)) 个邻域扰动样本
    ...
```

### Pattern 2: 内容寻址 prompt cache（续跑 + 零浪费）

**What:** `raw_responses/{prompt_hash}.json`（`prompt_hash = sha256({prompt, model, effort})`）。

**Why standard for this phase:** v1.0 已写出 3003 个 cache 文件。Phase 8 把 3000 旧样本 + 7000 新样本一起喂给 labeler，旧 3000 全部 cache hit（零 API token），新 7000 进 API。**关键：扩容不需要重标 v1.0**，且断电/重启零损失。

**Source:** `tsc_cycle/teacher/client.py:88-107` 已实现 atomic rename 写入。

### Pattern 3: sample_id-hash 决定性 split（DATA-03 复现）

**What:** `bucket = int.from_bytes(sha256(sample_id)[:8], "big") % 10`；bucket=0 进 val_id，其余进 train。OOD 永远 sticky 到 val_ood。

**Why:** 跨重新运行、跨 seed 变化、跨样本扩容，**已经在 train 的样本永远还在 train**。这是 DATA-03 "可复现 split" 的物理保证。

**Source:** `tsc_cycle/student/dataset.py:40-43`。

### Anti-Patterns to Avoid

- **重新生成 inputs.jsonl 的 sample_id**：sample_id 是 sha256(canonical_input)，输入不变 ID 不变；如果 v1.0 已标注的 3000 ID 变了，就丢失了 cache hit，浪费 ~$60 重标。**新生成的 7000 必须是新输入（新随机 seed），旧 3000 完全不动。**
- **packing=True / 多样本拼接进 SFT**：dataset.py 一个样本一行 parquet；不要为了"省空间"拼。
- **失败样本无限重试**：`teacher/labeler.py` 设计上 lint 失败直接进 `rejected.jsonl` 不重试。重试会过拟合到难例分布，且不省 token。Phase 8 必须保留这一行为。
- **把 v1.0 失败样本原样加入新训练集**：原始失败样本加进去会让模型直接学到那个样本的教师答案；正确做法是**邻域扰动**（同一难度类别但不同字段值），让模型学到"在这一类难例上的决策风格"。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAI 重试 / RateLimit / Retry-After | 自写 backoff 循环 | `tsc_cycle/teacher/client.py:189-211` | 已实现 RateLimit 不计入 retry budget；APITimeout/Connection/API/BadRequest 指数退避；都已被 v1.0 3000 样本压测验证 |
| reasoning_effort 静默降级检测 | 在 schema 上加 reasoning 字段 | `client.py:154-170` `require_reasoning_tokens_min=100` | 已实现，过小 reasoning_tokens 直接 reject |
| 同分布 KS 检验 | 自写 KS / EMD | `scripts/dist_check.py` + `scipy.stats.ks_2samp` | 已实现 5 字段全报表；扩到 10K 重跑即可 |
| 硬约束验证 | 自写 if/else | `tsc_cycle/constraint_lint.py::validate` | 已实现 7 类 violation 枚举 + LintResult；teacher labeler + eval 共用 |
| 候选输入唯一性 | 自写 dedupe | `hashing.sample_id` 用作 dedupe key + DB 一样的"已见集合" | 已实现 |
| 进度持久化 / 断点续跑 | 自写 checkpoint | `labeler.py:43-57` `_read_done_ids` 从 labeled+rejected jsonl 读 sample_id 集合 | 已实现，每个样本完成立即 flush |

**Key insight:** Phase 8 几乎所有复杂逻辑都已经在 v1.0 闭环里。Phase 8 的工程量集中在「数据来源扩展」和「报告/manifest 输出」这两个 thin layer。

## Common Pitfalls

### Pitfall 1: 教师 API 成本失控

**What goes wrong:** 10K 样本 @ ~1400 token/sample → ~14M tokens；按 GPT-5.5 high 名义价格 (CLAUDE.md 中 PRICE_OUTPUT_PER_M=10.00 USD/1M) 估算 ~$50-100 一次。多次重跑（比如 prompt 改了导致 cache 全 miss）会快速烧钱。

**Why it happens:** 任何对 prompt_builder.USER_TEMPLATE 的修改都会让 `prompt_hash` 全部失效。

**How to avoid:** 
1. Phase 7 已固化 `<end_working_out>` 协议，**Phase 8 严禁再改 prompt_builder**。任何文本变更都要在 plan 阶段被 quarantine。
2. 用 `--limit 50` smoke 先跑（已是 `run_pipeline.sh:29-35` 的标准做法），确认 ok≥45/50 后才放全量。
3. teacher_cost.json 落盘后立刻审计 `estimated_usd_total`；超预算（建议 $80 上限）立即停。

**Warning signs:** smoke 阶段 reject_rate > 0.10 或 cost_per_sample > $0.05。

### Pitfall 2: v1.0 失败样本回放导致泄漏

**What goes wrong:** 把 v1.0 OOD val 的失败 sample_id 直接放进 v2.0 训练集 → v2.0 评测时 OOD val 复用同一批 sample_id → 训练-评测泄漏 → "OOD lint 提升"是假的。

**Why it happens:** v1.0 的 OOD val_ood split 来自 `ood_inputs.jsonl`，每个样本有稳定 sample_id；如果 targeted 直接复用这些 ID，dataset.py 的 hash 桶会把它们都放进 `val_ood`（因为 split_hint=ood）。但教师标注后，它们就出现在 `labeled.jsonl` 里——而 eval 用的还是同一组 sample_id 跑泛化测试。

**How to avoid:** targeted 样本必须**生成新 sample_id**（即扰动后的 input 必须 hash 出新 ID）。dataset.py 现有的 leak check（`assert not (train_ids & val_ood_ids)`）只能查 set 重叠，不能查"同一难例的近邻样本"。Phase 8 plan 必须新增一条断言：`targeted` 样本的 sample_id 不与 `runs/20260507T032419Z/eval/per_sample.jsonl` 中任一 sample_id 重合。

**Warning signs:** `dataset_manifest.json` 中 `targeted_seed_overlap_count > 0`。

### Pitfall 3: reality.log 经验分布过窄导致 same-dist 实际是 narrow-OOD

**What goes wrong:** v1.0 dist_prior 的 phase_count ∈ {3,4,5}、min/max ∈ 5 个 modes。如果 Phase 8 直接 sample 10K 同分布，每个 mode 就有 ~1400 样本——**模式重复度极高**，QLoRA 容易过拟合到 5 个 (min,max) 组合。

**Why it happens:** dist_prior 是 reality.log 426 prompt 的统计，本身离散度不够支撑 7000 同分布样本。

**How to avoid:** 在 plan 中考虑把 "id" 重定义为"软同分布"——`range_modes_top` 抽样时除了前 10 mode（v1.0 做法），允许从前 30 mode 加权抽样；或对 `pred_wait` / `pred_saturation` 在原分布上加 ±5% 高斯噪声。仍然 KS-pass，但实际多样性更高。

**Warning signs:** `dist_check_report.md` 显示 same-dist KS p=1.0 across all fields（v1.0 表现），说明分布完全贴合参考——拟合度太高反而是过窄信号。

### Pitfall 4: 10K 样本可能撑爆 max_length

**What goes wrong:** v1.0 dataset_card 显示 p99=1100, max=1249（cap=4096，远不饱和）。但 OOD 样本扩到 2000 后，phase_count=7,8 的样本变多 → prompt 长度上升；teacher reasoning 在更难样本上也会更长（reasoning_tokens 中位 ~500，最高可 1000+）→ p99 可能升到 1500-2000。

**Why it happens:** v1.0 OOD 仅 300 样本，phase_count=7,8 累计仅 29 个；扩 6.7× 后会有 ~200 个高 phase_count 样本，对长度的尾部分布显著改变。

**How to avoid:** dataset.py 已经动态计算 p99 + buffer 64（`student/dataset.py:121-123`），cap 4096 还有充足余量。Plan 中应把 cap 暴露为参数；trainer 阶段（Phase 9）需注意若实际 max_length 升到 2000+，QLoRA 的 batch 配置可能要从 batch=4 降到 batch=2。

**Warning signs:** `dataset_card.md` 中 p99 > 1500 → 提示 Phase 9 重算显存。

### Pitfall 5: 标注成本估计变 0（PRICE 环境变量未设）

**What goes wrong:** `labeler.py:33-34` 用 env var `GPT5_5_INPUT_PER_M`/`GPT5_5_OUTPUT_PER_M`；如果 unset → 默认 1.25 / 10.00 USD/M。但实际 GPT-5.5 价格如果上游变了，落盘的 cost 就是错的。

**How to avoid:** Plan 中加一条：在跑 full labeling 前，把当时的实际 OpenAI pricing 写到 env var 或 config，避免 cost.json 给出 misleading 数字。

## Runtime State Inventory

> Phase 8 是数据扩容，主要是文件 IO 操作；但有以下现存运行时状态需要规划：

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `raw_responses/` 目录有 v1.0 的 3003 个 cache 文件（每个对应一个 `prompt_hash`）；`data/labeled.jsonl` 3000 行；`data/inputs.jsonl` 2700 + `data/ood_inputs.jsonl` 300；`data/labeled.jsonl.bak` 是 v1.0 备份 | **保留全部，不删**：cache hit 让 v1.0 的 3000 样本零成本进 v2.0 标注；`labeled.jsonl` 在 v2.0 中 append（labeler 用 `_read_done_ids` 跳过已标 ID） |
| Live service config | None — 没有外部服务（OpenAI API 走 `OPENAI_API_KEY` env，无项目内的 server） | None |
| OS-registered state | None — 没有 systemd/cron/Task Scheduler 任务 | None |
| Secrets/env vars | `OPENAI_API_KEY`（required）；`OPENAI_BASE_URL`（v1.0 走 codex proxy `http://148.135.118.86:8080`，见 `client.py:7`）；`GPT5_5_INPUT_PER_M` / `GPT5_5_OUTPUT_PER_M`（cost 估算用）；存放在 shell env，不在 git | **核对 BASE_URL 是否仍可用**：v1.0 跑完到现在过了 ~1 天，proxy 应仍在；plan 阶段可加一条 smoke "1 个样本 happy-path"先确认 |
| Build artifacts | None — 不涉及 pip 安装/二进制构建；tokenized/ parquet 是数据产物，不是 build artifact | None |

**关键续跑约束：** 如果 `data/inputs.jsonl` 中已有 sample_id 在新 seed 下被复制（即一个旧的 in-dist 样本恰好被新 seed 重新生成），labeler 会跳过（已 done）；这是好事不是 bug。但如果新一轮 sample_inputs.py 用了不同的输入 schema（比如改了 `_crossing_id` 字段），sample_id 会变，cache 失效。**Phase 8 plan 必须强制：sample_inputs 的 input dict schema 不变**——只允许 phase 数、字段值变。

## v1.0 失败样本回放——具体策略

来源文件：`runs/20260507T032419Z/eval/per_sample.jsonl`（1800 行 = 600 样本 × 3 backend）。

**字段：** `sample_id, backend, split_hint, lint_ok, violations, mae, exact_match, ...`

**v1.0 报告统计：**
- 总失败行数（lint_ok=False OR mae>5）：**558 / 1800**（约 30%）
- 去重到 sample_id 后：估计 ~150-200 个 unique 失败样本（多 backend 同一样本算一次）
- 都集中在 split_hint=ood
- 顶级失败模式：`above_max`、`below_min`、`mae=39-95s` 的极大数值偏离

**邻域扰动策略（建议）：**

```python
# 对每个失败 sample_id：
# 1. 查到原始 input（从 ood_inputs.jsonl 反查）
# 2. 应用以下扰动之一：
#    a. 字段轻扰：pred_wait *= U(0.9, 1.1), pred_saturation *= U(0.9, 1.1) （保持 saturation ∈ [0,1]）
#    b. 同 OOD 维度重采：如果原样本是 wait OOD，重抽 wait 在 OOD_WAIT_HIGH 范围
#    c. 范围扰：min_green ± 2, max_green ± 5（但不破坏 min<max）
# 3. n_targeted ≈ 1000；每个种子产生 ceil(1000/n_seeds) 个变体
# 4. 重新计算 sample_id（必然变，因为 input 变了）
# 5. 标 split_hint="id"（targeted 样本进入训练，**不**进 val_ood，避免泄漏）
```

**为什么 split_hint=id：** targeted 是给训练集补的，让模型在"v1.0 失败模式的邻域"上多看教师答案。OOD val 仍然来自纯 OOD 采样器（不带 targeted）以保证评测分布与 v1.0 可比（DATA-03 + Phase 10 EVAL-01 的"严格优于 98.7%"必须可比）。

## DATA-02 Report Schema

新增 `data/dataset_report.md`，建议字段：

```markdown
# Dataset Report (v2.0)

## Source Composition (DATA-01)
| Source | n_input | n_labeled | reject_rate |
|---|---|---|---|
| id | 7000 | 6850 | 2.1% |
| ood | 2000 | 1920 | 4.0% |
| targeted | 1000 | 970 | 3.0% |
| **Total** | **10000** | **9740** | **2.6%** |

## Field Distribution vs reality.log (KS test, scipy.stats.ks_2samp)
| Field | id KS p | ood KS p | targeted KS p |
|---|---|---|---|
| pred_wait | 0.99 | 1e-65 | 1e-22 |
| pred_saturation | 0.97 | 1e-50 | ... |
| ... | | | |

## Boundary Coverage (per OOD dimension)
| Dim | n_ood | n_targeted | reality_log 出现次数 |
|---|---|---|---|
| phase_count={2,6,7,8} | 470 | 38 | 0 |
| range_combo (new min/max) | 354 | ... | ... |
| ... | | | |

## v1.0 Comparison
| Metric | v1.0 | v2.0 | Δ |
|---|---|---|---|
| total_labeled | 3000 | 9740 | +6740 (+225%) |
| ood_labeled | 300 | 1920 | +1620 (6.4×) |
| phase_count=7,8 训练样本 | 29 | ~200 | +6.9× |
| reject_rate | X% | 2.6% | ... |
| 均长 token | 901 | ? | ... |
| 估计教师成本 | $Y | $Y'  | ... |

## Targeted Sample Source (v1.0 失败样本回放)
- 来源 file: `runs/20260507T032419Z/eval/per_sample.jsonl`
- v1.0 失败 sample_id (lint_ok=F OR mae>5): N=...
- 扰动策略: per_sample 字段 ±10%
- 新 sample_id 与 v1.0 OOD val_ood 重叠数: 0  ← 必须
```

## Split Metadata 字段（DATA-03）

新增 `data/split_manifest.json`：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-08T...",
  "input_version": {
    "inputs_jsonl_sha256": "...",
    "ood_inputs_jsonl_sha256": "...",
    "targeted_inputs_jsonl_sha256": "...",
    "dist_prior_sha256": "..."
  },
  "labeled_version": {
    "labeled_jsonl_sha256": "...",
    "labeled_n": 9740
  },
  "seeds": {
    "sample_inputs_seed": 42,
    "targeted_seed": 1337,
    "split_bucket_n": 10
  },
  "splits": {
    "train": {"n": ..., "id_count": ..., "targeted_count": ..., "ood_count": 0},
    "val_id": {"n": ..., ...},
    "val_ood": {"n": ..., ...}
  },
  "reproduction": {
    "command": "python -m tsc_cycle.sample_inputs --n-id 7000 --n-ood 2000 --seed 42 && python -m tsc_cycle.sample_inputs --targeted ... && python -m tsc_cycle.teacher.labeler && python -m tsc_cycle.student.dataset",
    "git_commit": "...",
    "teacher_model": "gpt-5.5",
    "teacher_effort": "high"
  }
}
```

## Code Examples

### v1.0 失败样本读取（targeted seed selection）

```python
# Source: 自写，基于 runs/20260507T032419Z/eval/per_sample.jsonl 实测格式
import json
from pathlib import Path

def load_failure_seeds(eval_path: Path) -> set[str]:
    """Returns set of v1.0 sample_ids that any backend failed on."""
    seeds = set()
    for line in eval_path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        is_lint_fail = rec.get("lint_ok") is False
        is_high_mae = (rec.get("mae") or 0) > 5.0
        if is_lint_fail or is_high_mae:
            seeds.add(rec["sample_id"])
    return seeds

def load_v1_inputs_by_id(ood_inputs: Path, id_inputs: Path) -> dict[str, dict]:
    """Returns sample_id -> input dict, from v1.0 inputs files."""
    out = {}
    for p in [ood_inputs, id_inputs]:
        for line in p.read_text().splitlines():
            obj = json.loads(line)
            out[obj["sample_id"]] = obj
    return out
```

### Resume-safe append-only labeled.jsonl（已存在，仅参考）

```python
# Source: tsc_cycle/teacher/labeler.py:91-148 (existing)
done = _read_done_ids(Path(args.labeled), Path(args.rejected))
pending = [s for s in all_inputs if s["sample_id"] not in done]
# ... ThreadPoolExecutor(max_workers=10) ...
# every successful future:
with lab_lock:
    lab_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    lab_f.flush()  # critical: flush after each, so SIGKILL doesn't lose state
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.0 二元 source（id + ood） | v2.0 三元 source（id + ood + targeted） | Phase 8 新增 | 失败模式邻域补强；预期 OOD lint 99.3% → ≥99.5% |
| v1.0 split=80/10/10 of 3000 | v2.0 split=80/10/10 of ~9740 | Phase 8 扩容 | train ~7800; val_id ~970; val_ood ~1920 |
| v1.0 prompt cache 3003 文件 | v2.0 cache 复用 + 增量 7000 | Phase 8 续跑 | API cost ≈ 70% 全新（v1.0 的 3000 cache 全 hit） |
| `</end_working_out>` 协议 | `<end_working_out>` 协议 (Phase 7) | 已迁移 | Phase 8 sample_inputs / labeler / dataset 都已用新协议（无变化） |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OPENAI_BASE_URL proxy `http://148.135.118.86:8080` 仍可用 | Runtime State | 高：必须 plan 加 1-sample smoke 验证 |
| A2 | GPT-5.5 high 名义定价 $1.25/M input + $10.00/M output 仍有效 | Pitfalls #5 | 中：cost.json 数字 misleading，但不影响标注本身 |
| A3 | v1.0 失败 sample_id 数量去重后约 150-200 | "v1.0 失败样本回放" | 低：估算用，实际数会驱动 targeted 扰动倍数 |
| A4 | 三源比例 7:2:1 是合适的 | Pattern 1 | 中：经验估计；可在 dataset_report 后据实调整。但 OOD 训练样本占比从 v1.0 的 10% (300/3000) 提到 20% (2000/10000) 是关键，不应再降 |
| A5 | 扩到 10K 后 token p99 仍在 cap 4096 内 | Pitfall #4 | 低：v1.0 p99=1100，cap=4096 余量 3.7×；但需 dataset.py 实测确认 |
| A6 | `<end_working_out>` 协议（Phase 7）已完全替代旧协议；Phase 8 不需要再改 prompt | Pitfall #1 | 低：Phase 7 verified；REQUIREMENTS.md TAG-01/TAG-02 已 Complete |

**用户需要在 plan-phase 前确认：** A1（proxy 可用性）和 A4（7:2:1 比例是否同意）。

## Open Questions

1. **v1.0 失败样本中"高 MAE"阈值** — 目前建议 mae>5；但 v1.0 OOD MAE 均值已是 7.7s，所以 mae>5 会涵盖 ~50% OOD 样本。是否用更严格阈值（如 mae>10 或 lint_ok=False only）？
   - 我们知道：mae>5 触发 558 行（30%）；lint_ok=False 触发 ~12 行（很少）
   - 不清楚的：到底要 targeted 多大规模才有边际效用
   - 建议：plan 中两档 — `lint_ok=False`（约 5 个 unique seed）+ `mae>10`（约 30-50 个 seed），合计 ~50 个 seed，每个种 20 个邻域 = 1000 targeted

2. **是否需要 v1.0 标注 cache 兼容性测试** — Phase 7 把协议从 `</end_working_out>` 改成 `<end_working_out>`，但 v1.0 raw_responses 缓存的教师输出**仍是旧格式**（因为缓存时 Phase 7 还没做）。
   - 检查方式：随机抽 10 个 cache 文件 grep `</end_working_out>` vs `<end_working_out>`
   - 如果旧格式：`labeler.py` 调 `parse_assistant_output` 时 `LEGACY_THINK_CLOSE in text` 会让 reject 全部旧 cache → 所有 3000 样本要重标 → cost +$60
   - **plan 必读**：先抽样 cache 确认协议；如果是旧的，要么 (a) 接受重标全 3000，(b) 写一次性迁移脚本把 cache 中的 `</end_working_out>` 替换成 `<end_working_out>` 并保持 prompt_hash 不变

3. **如果 v2.0 训练集变大后 reject_rate > 5%，是否调整 reasoning_tokens_min** — 当前 100；OOD 难题可能让教师 silent-downcast 到 reasoning_tokens=80 但仍然给出正确解。
   - 不清楚的：OOD 的合理 reasoning_tokens 下限
   - 建议：plan 中加一步分析 v1.0 cache 的 reasoning_tokens 分布，画 histogram，决定是否降到 80

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 venv (`/home/samuel/dgx-spark-setup/.venv`) | 全部 | ✓（v1.0 已用） | 3.12 | — |
| openai package | teacher.client | ✓ | >=1.50.0（在 pyproject） | — |
| OpenAI API key (env `OPENAI_API_KEY`) | teacher.labeler | ⚠ 需 plan 阶段确认 | — | 无 fallback：必须有 |
| OpenAI proxy `http://148.135.118.86:8080` | teacher.client | ⚠ 假设可用，未实地探测 | — | 切回官方 OpenAI（要 plan 中预留 1-sample smoke 探测） |
| pyarrow | student.dataset | ✓ | >=15 | — |
| scipy | scripts/dist_check | ✓ | >=1.13 | — |
| transformers (Qwen3 tokenizer) | student.dataset | ✓（v1.0 已用） | >=4.56.2 | — |
| reality.log（dist_prior 源） | sample_inputs | ✓（已 fit 到 dist_prior.json） | — | dist_prior.json 直接用，不需重 fit |
| `runs/20260507T032419Z/eval/per_sample.jsonl` | sample_targeted | ✓ 1800 行 | — | 无 fallback：v1.0 失败样本必须从这里读 |
| `data/inputs.jsonl` + `data/ood_inputs.jsonl` | sample_targeted seed 反查 | ✓ | — | — |
| `raw_responses/` cache | teacher.labeler 续跑 | ✓ 3003 文件 | — | 没缓存就全部重标（+$60 但 functional） |

**Missing dependencies with no fallback:** None（OPENAI_API_KEY 是 plan 时必须 export 的运行期需求，不算 fallback 缺口）。

**Missing dependencies with fallback:** None。

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 + pytest-xdist >=3.5.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, addopts="-q") |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | sample_inputs 三源采样产生 10K 候选，三类比例可读 | unit | `pytest tests/test_sample_inputs.py::test_three_source_proportions -x` | ❌ Wave 0 |
| DATA-01 | targeted 样本 sample_id 与 v1.0 OOD val_ood 不重叠 | unit | `pytest tests/test_sample_inputs.py::test_targeted_no_leak -x` | ❌ Wave 0 |
| DATA-01 | targeted 种子全部来自 lint_ok=False ∪ mae>thresh | unit | `pytest tests/test_sample_inputs.py::test_targeted_seed_provenance -x` | ❌ Wave 0 |
| DATA-02 | dataset_report.md 包含三源比例、KS 表、v1.0 对比表 | unit | `pytest tests/test_dataset_report.py::test_report_sections -x` | ❌ Wave 0 |
| DATA-02 | dist_check_report 同分布 KS p>0.05 across all fields | integration | `pytest tests/test_dist_check.py::test_id_passes_ks -x`（小规模 fixture） | ❌ Wave 0 |
| DATA-03 | split_manifest.json schema 完整（input_version + labeled_version + seeds + splits） | unit | `pytest tests/test_split_manifest.py::test_schema -x` | ❌ Wave 0 |
| DATA-03 | 同 seed 重跑 sample_inputs → 完全相同 sample_id 集合 | unit | `pytest tests/test_sample_inputs.py::test_deterministic -x` | ❌ Wave 0 |
| DATA-03 | dataset.py split 桶哈希决定性（同一 sample_id 永远同一 split） | unit | `pytest tests/test_dataset.py::test_split_bucket_stable -x`（增强既有） | ❌ Wave 0 |
| DATA-03 | labeler 续跑跳过 done sample_id（不重复标注） | integration | `pytest tests/test_labeler_resume.py::test_skip_done -x`（mock client） | ❌ Wave 0 |

**已存在测试**：
- `tests/test_constraint_lint.py` — 覆盖硬约束 lint（不需改）
- `tests/test_prompt_builder.py` — 覆盖 Phase 7 协议（不需改）
- `tests/test_hashing.py` — 覆盖 sample_id 决定性（不需改）

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`（< 10s，因为 unit + small fixture）
- **Per wave merge:** `pytest tests/ -q`（全套）
- **Phase gate:** 完整跑 `bash scripts/run_pipeline.sh` 的 Phase 3（teacher 标注 50-sample smoke）+ dataset build 后跑 `pytest tests/`

### Wave 0 Gaps

- [ ] `tests/test_sample_inputs.py` — 覆盖 DATA-01 + DATA-03 决定性
- [ ] `tests/test_dataset_report.py` — 覆盖 DATA-02 报告字段
- [ ] `tests/test_dist_check.py` — 覆盖 dist_check 在 fixture 数据上的 KS 行为
- [ ] `tests/test_split_manifest.py` — 覆盖 DATA-03 manifest schema
- [ ] `tests/test_labeler_resume.py` — 覆盖断点续跑（mock TeacherClient）
- [ ] `tests/conftest.py` — 共享 fixture：mini dist_prior（5 phase modes）+ mini eval per_sample（10 行）+ mini labeled jsonl（10 行）
- [ ] Framework install: 已在 dev extras（`uv pip install -e '.[dev]'` 即可），无 install 阻塞

## Security Domain

> 此 phase 涉及外部 API 调用（OpenAI），需评估输入处理 + 凭证。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | OPENAI_API_KEY via env var；不入 git；`client.py:80-82` 已实现 |
| V3 Session Management | no | API 无 session |
| V4 Access Control | no | 单用户本机 |
| V5 Input Validation | yes | constraint_lint + JSON schema 隐式校验（`json.loads` + key check） |
| V6 Cryptography | no | 不存敏感数据 |

### Known Threat Patterns for {teacher API + offline data pipeline}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key 泄漏到日志/cost.json/cache | Information Disclosure | client.py 不写 key 到 raw / usage; cost.json 只含 token 数；建议 plan 中加 `gitignore raw_responses/, runs/, data/labeled.jsonl`（应已有） |
| 教师返回恶意 JSON 触发 parser bug | Tampering | `parse_assistant_output` 已 catch JSONDecodeError/ValueError/TypeError；`constraint_lint` 拒所有非 dict / 非 int |
| OPENAI_BASE_URL 被改向钓鱼 proxy | Spoofing | env var 控制；plan 中明确生产环境 base_url 应在 README 列出；任何改动需 review |
| 大规模 API 调用 DoS 自身预算 | DoS（钱包） | smoke test 50 → 限流；plan 中加 cost upper bound 检查（`if estimated_usd_total > 80: abort`） |

## Project Constraints (from CLAUDE.md)

- **教师并发上限 10 worker** — 已在 `labeler.py:68 default=10`，不可放大
- **教师必须通过硬约束 lint** — 已在 `labeler.py:120-124`
- **思考标签必须用词表外多 sub-token** — Phase 7 已迁移；`tokenizer_check` 在 `student/dataset.py:88-92` 跑
- **不得 add_special_tokens 把自定义标签加 vocab** — 现有 prompt_builder 走文本不动 vocab
- **不得 packing=True** — 已在 dataset.py 一行一样本
- **预算上限 3000 样本是设计点；超出需另议** — Phase 8 明确扩到 10K，已在 ROADMAP 中作为 milestone v2.0 决策；CLAUDE.md 该项需在 milestone 完成后更新
- **数据生成单独 4-6h 阶段** — Phase 8 时间预期：sample 阶段 < 5min；teacher 标注阶段 ≈ 2-4h（10K 样本 / 10 worker / ~10s per sample）
- **每页 PDF 单独读取（用户 global 规则）** — Phase 8 不涉及 PDF
- **回复用简体中文（用户 global 规则）** — RESEARCH.md 大量中文，符合

## Sources

### Primary (HIGH confidence)

- `/home/samuel/TSC_CYCLE/tsc_cycle/teacher/labeler.py` — 已实现 10 worker / cache / lint / reject 全链
- `/home/samuel/TSC_CYCLE/tsc_cycle/teacher/client.py` — 已实现 Responses API + reasoning gate + atomic cache
- `/home/samuel/TSC_CYCLE/tsc_cycle/sample_inputs.py` — 已实现 in-dist + 7 维 OOD 采样
- `/home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py` — 已实现 sample_id-hash split + dataset card
- `/home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py` — 已实现 7 类 violation
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` — Phase 7 已迁移 `<end_working_out>`
- `/home/samuel/TSC_CYCLE/scripts/dist_check.py` — KS test 框架
- `/home/samuel/TSC_CYCLE/scripts/run_pipeline.sh` — 现有 phase 3-6 顺序驱动模板
- `/home/samuel/TSC_CYCLE/data/labeled.jsonl` (3000 行) + `/home/samuel/TSC_CYCLE/raw_responses/` (3003 文件) — v1.0 实测数据，可直接复用
- `/home/samuel/TSC_CYCLE/runs/20260507T032419Z/eval/per_sample.jsonl` (1800 行) — v1.0 失败种子来源，DATA-01 targeted 必读
- `/home/samuel/TSC_CYCLE/runs/20260507T032419Z/eval/report.md` — v1.0 baseline 数字（98.7% / 99.3% / MAE 7.7-7.9s）
- `/home/samuel/TSC_CYCLE/data/dist_check_report.md` — v1.0 KS test 结果模板
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — 教师 API 模式、并发约束、硬约束 lint 强制要求

### Secondary (MEDIUM confidence)

- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/MEMORY.md` — Qwen3 tokenizer 标签语义冲突教训（不直接改 Phase 8，但锁定 prompt_builder 不可改）

### Tertiary (LOW confidence)

- GPT-5.5 实时定价（CLAUDE.md PRICE 默认值是 placeholder）— A2 假设

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 全部代码已存在并通过 v1.0 端到端验证
- Architecture: HIGH — 三源混合是 v1.0 二元的直接扩展，复用 80% 既有代码
- Pitfalls: HIGH — 5 项中 4 项有 v1.0 实测数据支撑（成本 / split leak / 长度 / cache 一致性）
- 三源比例 (7:2:1): MEDIUM — 经验估计，需用户确认

**Research date:** 2026-05-08
**Valid until:** 2026-06-08（30 天，OpenAI API 路径稳定；如果 BASE_URL 或 pricing 变需重审）

## RESEARCH COMPLETE

**Phase:** 8 - 10K 混合数据扩容与教师标注
**Confidence:** HIGH

### Key Findings

1. **80% 代码已就位**：`sample_inputs.py` / `teacher/labeler.py` / `teacher/client.py` / `student/dataset.py` / `constraint_lint.py` 在 v1.0 已端到端验证；Phase 8 主要是扩展（targeted 源 + manifest + report）而非新建。
2. **v1.0 cache 高复用价值**：`raw_responses/` 已 3003 文件，扩到 10K 时旧 3000 个 sample_id cache 全 hit（前提：prompt_builder 不动），节省约 30% API 成本。**但需先抽样 verify cache 内容是新协议 `<end_working_out>` 还是旧 `</end_working_out>`**——这是 Phase 7 迁移留下的潜在地雷（Open Question 2）。
3. **v1.0 失败样本源已确认**：`runs/20260507T032419Z/eval/per_sample.jsonl` 1800 行可读；按 lint_ok=False ∪ mae>5 过滤约 558 行，去重 sample_id 估 ~150-200 个失败种子。
4. **关键防泄漏断言**：targeted 样本 sample_id 必须与 v1.0 OOD val_ood sample_id 完全不重叠（dataset.py 现有 leak check 不覆盖此情形，plan 必须补单测）。
5. **建议三源比例 7:2:1**（id 7000 / ood 2000 / targeted 1000），把 OOD 训练样本从 v1.0 的 300 扩到 2000（6.7×），是 v2.0 OOD lint 严格 > 98.7% 的物理基础。

### File Created

`/home/samuel/TSC_CYCLE/.planning/phases/08/08-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | 全部库与版本已在 v1.0 验证 |
| Architecture | HIGH | 三源是 v1.0 二元的最小增量 |
| Pitfalls | HIGH | 5 项中 4 项有 v1.0 实测背书 |
| 三源比例 7:2:1 | MEDIUM | 经验估计，需用户确认 |
| OpenAI proxy 仍可用 | MEDIUM | 假设 v1.0 用过的 base_url 当前仍 live；plan 加 1-sample smoke 验证 |

### Open Questions

1. v1.0 raw_responses cache 中是 `<end_working_out>` 还是 `</end_working_out>`？（影响是否要重标 v1.0 全部 3000 样本）
2. targeted 失败种子阈值 mae>5 还是 mae>10？（影响 targeted 样本的"难度浓度"）
3. 是否调整 reasoning_tokens_min（默认 100）以减小 OOD 题目的误拒率？

### Ready for Planning

研究完成。Planner 可基于以下 file change map 生成 PLAN：

**新增文件：**
- `data/targeted_inputs.jsonl`
- `data/dataset_manifest.json`（按 §"DATA-01 source composition" 字段）
- `data/dataset_report.md`（按 §"DATA-02 Report Schema"）
- `data/split_manifest.json`（按 §"Split Metadata 字段"）
- `tests/test_sample_inputs.py`（DATA-01 + DATA-03 决定性 + targeted 防泄漏）
- `tests/test_dataset_report.py`
- `tests/test_dist_check.py`
- `tests/test_split_manifest.py`
- `tests/test_labeler_resume.py`
- `tests/conftest.py`（共享 fixture）

**扩展现有文件：**
- `tsc_cycle/sample_inputs.py`：加 `sample_targeted()` + 在 `main()` 加 `--targeted-eval-path` / `--n-targeted` 参数
- `tsc_cycle/manifest.py`（占位文件）：实现 `build_dataset_manifest()` 写 `data/dataset_manifest.json` 和 `build_split_manifest()` 写 `data/split_manifest.json`
- `tsc_cycle/student/dataset.py`：在 `main()` 末尾调用 `build_split_manifest()`，并写 `data/dataset_report.md`
- `tsc_cycle/teacher/labeler.py`：加 `--targeted-inputs data/targeted_inputs.jsonl` 参数，把 targeted 也并入 `all_inputs`
- `scripts/dist_check.py`：加 targeted 文件的 KS 报告
- `scripts/run_pipeline.sh`：在 phase 3 前插入新的 sample_inputs 步骤（生成 id + ood + targeted 三个文件）

**不动的文件：**
- `tsc_cycle/prompt_builder.py`（Phase 7 已锁，不动！cache hit 的命脉）
- `tsc_cycle/constraint_lint.py`
- `tsc_cycle/teacher/client.py`
- `tsc_cycle/hashing.py`
- `tsc_cycle/distribution_fit.py`
- `data/dist_prior.json`（reality.log fit 结果，不重 fit）
- `tests/test_constraint_lint.py` / `test_prompt_builder.py` / `test_hashing.py`
