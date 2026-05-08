# Architecture Research — v3.0 9B 基座切换

**Domain:** LLM 蒸馏离线批处理流水线（4B → 9B 学生基座切换；其余 stage 复用 v1.0）
**Researched:** 2026-05-08
**Confidence:** HIGH（v1.0 流水线已 SHIPPED；变更面集中在 Stage 4 训练参数 + Stage 6 评测对比表；llama.cpp `Qwen3_5ForCausalLM` 已在本机仓库注册）

---

## TL;DR — 变更分类总览

| Stage | v1.0 组件 | v3.0 状态 | 影响面 |
|-------|-----------|-----------|--------|
| 1. distribution_fit | `tsc_cycle/sample_inputs.py`, `distribution_fit.py` | **(a) 完全复用** | 0 |
| 1'. prompt_builder（含 Phase 7 标签迁移） | `tsc_cycle/prompt_builder.py` | **(a) 完全复用**（仅 tokenizer 重新做 sanity gate） | 0 |
| 2. sample_inputs（OOD 扩展） | `tsc_cycle/sample_inputs.py` | **(a) 完全复用**（输入分布与基座无关） | 0 |
| 3. teacher_labeler | `tsc_cycle/teacher/{client,labeler}.py` + `data/labeled.jsonl` | **(a) 完全复用**（教师固定 GPT-5.5 high；3000 已通过 lint 的样本可直接喂） | 0；可选重生成只为新 prompt 模板 |
| 4. dataset_builder | `tsc_cycle/student/dataset.py` | **(b) 参数调整**（重新 tokenize：新 tokenizer + 新 p99 估计；`MODEL_NAME` 常量改 9B） | 小 |
| **4. trainer** | `tsc_cycle/student/train.py` | **(b) 参数调整 + 强制 batch=1**（QLoRA 配置不变；`per_device_batch_size=1`，`grad_accum` 扩到 32–64；`max_seq_length` 由 dataset 重估；目标模块需核实 Qwen3.5 GDN 层是否同名） | 中 |
| 4'. tokenizer_check | `tsc_cycle/tokenizer_check.py`, `student/tokenize_sanity.py` | **(b) 参数调整**（基座换了，需要对 Qwen3.5 tokenizer 重新跑一次：自定义标签是否 multi-token、是否与原生 `<think>` 冲突；vocab 248320 而非 151936） | 小 |
| 5. merge | `tsc_cycle/student/parity_merge.py` | **(a) 完全复用**（PEFT `merge_and_unload` 与基座无关） | 0 |
| **6. export gguf** | `tsc_cycle/student/export_gguf.py` + 本机 llama.cpp | **(a) 完全复用**（`Qwen3_5ForCausalLM` 已注册在 `convert_hf_to_gguf.py:5036`；llama-quantize Q4_K_M 与基座无关） | 0；只需冒烟一次确认 |
| **7. evaluator** | `tsc_cycle/eval/run_eval.py` 等 | **(c) 需要新增对比层**（v3.0 baseline = v1.0 q4_K_M GGUF，需要把它作为第 4 个 variant 拉进 matrix；新增 ratio_vs_v1 列；report.md 新增 v3.0/v1.0 对比章节） | 中 |
| 7'. decision gate | `tsc_cycle/eval/decision.py` | **(b) 参数调整**（GO/NO-GO 阈值现在是相对 v1.0 而非绝对值；阈值需与里程碑目标对齐） | 小 |

**核心发现：流水线骨架完全可复用，变更高度集中在 (训练 batch 配置 + tokenizer sanity 重测 + 评测对比表)。无任何 stage 必须 (c) 重写或 (d) fallback。**

---

## Standard Architecture（v3.0，沿用 v1.0 6-stage 蒸馏流水线）

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 1: SAMPLER (offline, CPU, < 5 min)              [REUSE from v1.0]     │
│    reality.log ──► distribution_fit ──► dist_prior.json                       │
│    dist_prior.json ──► sample_inputs ──► inputs.jsonl + ood_inputs.jsonl     │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 2: TEACHER LABELER  (4-6h, ≤10 worker)         [REUSE labeled.jsonl]  │
│    inputs.jsonl ──► prompt_builder ──► OpenAI GPT-5.5 high ──► raw_responses │
│                                          │                                    │
│                                          ▼                                    │
│                                    constraint_lint  ──► labeled.jsonl        │
│   v1.0 已有 ~2700+ valid 样本（Phase 3 SHIPPED）；v3.0 默认 reuse              │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 3: DATASET BUILDER (CPU, < 10 min)             [RE-TOKENIZE for 9B]   │
│    labeled.jsonl ──► split (80/10/10, seed=42 LOCKED)                         │
│      ──► tokenize via Qwen3.5-9B tokenizer (新 vocab 248320) ──► arrow        │
│    ※ split seed 必须与 v1.0 一致，确保 OOD val 集对齐 v1.0 baseline           │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 4: TRAINER (GPU, ≤ 6h on DGX Spark GB10)       [PARAM CHANGE]         │
│    HF Dataset ──► QLoRA r=64 SFT                                              │
│      base_model = Qwen/Qwen3.5-9B            ← 唯一架构性变更                │
│      per_device_batch_size = 1               ← 用户硬约束（9B 显存压力）      │
│      gradient_accumulation_steps = 32 (目标 effective batch 32, 沿用 v1.0)    │
│      attn_implementation = "sdpa"            ← 沿用                           │
│      bf16 = True                             ← 沿用                           │
│      target_modules = [q,k,v,o,gate,up,down] ← 需 verify Qwen3.5 GDN 层名    │
│      ──► runs/{ts}/adapter/ (final LoRA)                                      │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 5: EXPORTER (CPU + small GPU, ~30 min)         [REUSE]                │
│    adapter/ ──► merge_lora.py ──► merged_fp16/ (HF safetensors)              │
│             ──► convert_hf_to_gguf.py ──► model.fp16.gguf                    │
│             ──► llama-quantize Q4_K_M ──► model.q4_K_M.gguf                  │
│   ※ Qwen3_5ForCausalLM 已注册在本机 llama.cpp/convert_hf_to_gguf.py:5036     │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 6: EVALUATOR (GPU + llama.cpp, ≤ 1h)           [ADD v1.0 BASELINE]    │
│    val.jsonl + ood_val.jsonl                                                 │
│      ──► generate (HF bf16 v3, GGUF q4_K_M v3, GGUF q4_K_M v1.0 baseline)    │
│      ──► gen_cache/{variant}/{hash}.json                                     │
│      ──► metrics: hard_constraint_pass / MAE_vs_teacher / ood_gap /          │
│                    reasoning_keyword_recall  + NEW ratio_vs_v1               │
│      ──► reports/{ts}/report.md  +  decision.md                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (v3.0 deltas only)

| Component | v1.0 责任 | v3.0 变更 |
|-----------|-----------|-----------|
| `prompt_builder` | 渲染 user prompt + 思考标签包装 | **不变**（Phase 7 标签协议迁移已锁定 `<end_working_out>` 闭合形式，与 v3.0 兼容） |
| `tokenizer_check` | 启动断言：自定义标签 multi-token；原生 `<think>` id 不出现 | **重跑 1 次**（Qwen3.5 vocab 248320 ≠ Qwen3 vocab 151936；MEMORY 已验证 Qwen3 行为，Qwen3.5 必须独立验证；如果 `<start_working_out>` 在新 vocab 中变成单 token，则触发 v2.0 同款语义冲突，**这是切 9B 的最大单点风险**） |
| `student/dataset.py` | 用 Qwen3-4B-Thinking-2507 tokenizer 一次性 tokenize 落 arrow | 把 `MODEL_NAME` 常量切到 `Qwen/Qwen3.5-9B`；重跑 `dataset.py` 估 p99 token 长度（9B tokenizer 与 4B 不同 → max_length 可能变化） |
| `student/train.py` | QLoRA r=64, epoch=2, bs=4×grad_accum=8 (eff 32) | `MODEL_NAME` 切 9B；CLI 默认 `--batch-size 1 --grad-accum 32`；其他不变；**target_modules 需要核实**（Qwen3.5 GDN 层可能不叫 `q_proj/k_proj`） |
| `student/export_gguf.py` | 调本机 `convert_hf_to_gguf.py` + `llama-quantize` | **不变**（已确认架构注册）；只需在第一次跑通后冒烟验证生成 token 与 HF 一致 |
| `eval/run_eval.py` | 三 variant matrix：HF bf16 / GGUF bf16 / GGUF q4_K_M（同一个模型三精度） | **结构延伸**：把 v1.0 q4_K_M GGUF 作为第 4 个 variant 加入 matrix；指标层加 `ratio_vs_v1 = v3_metric / v1_metric` 计算 |
| `eval/decision.py` | 单一阈值 `q4 vs fp16 ratio ≥ 0.95` | 增加 `v3_q4 vs v1_q4 ratio ≥ 1.0`（或里程碑约定的「9B 升级必须带来可验证收益」阈值） |

---

## Recommended Project Structure（v3.0 增量）

```
TSC_CYCLE/
├── tsc_cycle/                          # 几乎不动
│   ├── prompt_builder.py               # [REUSE, Phase 7 已迁移]
│   ├── tokenizer_check.py              # [RE-RUN once on Qwen3.5 tokenizer]
│   ├── student/
│   │   ├── dataset.py                  # [PARAM] MODEL_NAME → Qwen3.5-9B
│   │   ├── train.py                    # [PARAM] MODEL_NAME, default --batch-size 1 --grad-accum 32
│   │   ├── tokenize_sanity.py          # [REUSE] auto-follows prompt_builder constants
│   │   ├── export_gguf.py              # [REUSE]
│   │   └── parity_*.py                 # [REUSE]
│   ├── teacher/                        # [REUSE entirely]
│   ├── eval/
│   │   ├── run_eval.py                 # [EXTEND] add v1_baseline variant
│   │   ├── compute_metrics.py          # [EXTEND] add ratio_vs_v1 column
│   │   ├── decision.py                 # [PARAM] dual-threshold gate
│   │   └── ...
│   └── ...
├── data/
│   ├── labeled.jsonl                   # [REUSE; v1.0 教师标签]
│   ├── tokenized/                      # [REBUILD; 9B tokenizer]
│   └── splits/                         # [REUSE seed=42 split indices]
├── runs/
│   ├── 20260507T032419Z/               # v1.0 SHIPPED artifact (gguf/model.q4_K_M.gguf 用作 baseline)
│   └── {v3.0 ts}/                      # 新一轮
└── .planning/
    └── milestones/
        ├── v1.0-ROADMAP.md
        ├── v2.0-abandoned/
        └── v3.0-...                    # 本次里程碑
```

### Structure Rationale

- **`labeled.jsonl` 不重生成**：教师未变（GPT-5.5 high），prompt 模板未变（Phase 7 协议锁定），硬约束未变 → labeled.jsonl 是基座无关的纯数据资产；重新调 GPT-5.5 既费钱又会引入随机性，让 v1.0/v3.0 可比性下降。
- **split seed=42 必须锁死**：v3.0 评测要把 v1.0 q4_K_M 拉进 matrix 跑同一份 ood_val；如果 split 不同则数字不可比。
- **runs/{v3 ts}/ 与 runs/20260507T032419Z/ 并存**：评测代码读两条路径（本轮 adapter 产物 + v1.0 GGUF artifact）；不要把 baseline 复制进新 run。
- **不引入新 package**：v3.0 是参数变更而非架构演进；新 package 反而增加 import 表面与 GSD 文档负担。

---

## Architectural Patterns（v3.0 特有）

### Pattern 1: Frozen-Data, Floating-Base Distillation Refresh

**What:** 教师标签固化在 `data/labeled.jsonl`，基座升级时只重做 (tokenize + train + export + eval)。
**When to use:** 同教师同任务，仅换学生基座的蒸馏迭代；本里程碑标准模式。
**Trade-offs:**
- 优势：成本可控（不再调 GPT-5.5）+ v1.0/v3.0 数字严格可比（同样本同教师答案）。
- 劣势：若新 tokenizer 让某些样本 max_seq_length 显著超界，需要丢弃；需在 dataset 重建期间统计。

**Example:**
```python
# tsc_cycle/student/dataset.py 修改面（仅常量）
MODEL_NAME = "Qwen/Qwen3.5-9B"   # was "Qwen/Qwen3-4B-Thinking-2507"
# 其余 tokenize_one / split / arrow 写入逻辑全部不动
```

### Pattern 2: Shared-Cache, Multi-Run Evaluation

**What:** v1.0 baseline 不重跑生成，从 `runs/20260507T032419Z/eval/gen_cache/gguf_q4km/*.json` 直接载入历史结果做对比。
**When to use:** 跨里程碑回归对比；只要评测的 prompt 集合（300 id + 300 ood, seed=42）一致。
**Trade-offs:** 需要保证 v1.0 gen_cache 仍在磁盘（要点入 milestone checklist）。
**Example:**
```python
# eval/run_eval.py 增量
VARIANTS = {
    "hf_bf16_v3":  HFBackend(model_dir="runs/{v3_ts}/export/merged_fp16"),
    "gguf_q4_v3":  GGUFBackend(path="runs/{v3_ts}/export/model.q4_K_M.gguf"),
    "gguf_q4_v1_baseline": GGUFBackend(
        path="runs/20260507T032419Z/gguf/model.q4_K_M.gguf",
        cache_dir="runs/20260507T032419Z/eval/gen_cache/gguf_q4km",  # reuse
        read_only=True,
    ),
}
```

### Pattern 3: Tokenizer Sanity Gate as Phase 0 Hard Stop

**What:** 在做任何训练投入之前（甚至 dataset 重建之前），先跑 `tokenizer_check.py` 对 Qwen3.5 tokenizer：
1. `<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 全部 `multi_token=True`；
2. 原生 `<think>` / `</think>` 的 token id 与训练数据里出现的子 token 不冲突；
3. vocab size 与模型 config 一致（Qwen3.5 = 248320 padded）。
**When to use:** 任何换基座 tokenizer 的第一步。
**Trade-offs:** 多 5 秒；但若 Qwen3.5 把某个标签合并成单 token（不应发生但必须验证），整个 v3.0 假设崩塌，省下 6h 训练。
**Example:** 见 v1.0 `tsc_cycle/tokenizer_check.py`，仅需把 `MODEL_NAME` 改 9B。

### Pattern 4: Three-Threshold Decision Gate

**What:** v3.0 决策门不是一个阈值，而是三个：
1. `q4_v3 vs fp16_v3 ratio ≥ 0.95`（量化无崩塌，沿用 v1.0 阈值）
2. `q4_v3 vs q4_v1 ratio ≥ 1.00`（9B 升级带来可验证收益，里程碑核心问题）
3. `q4_v3 hard_constraint_pass ≥ 98%`（绝对水平不退化）
**When to use:** 跨基座升级的 GO/NO-GO 决策；任一不达标都触发讨论而非自动 GO。
**Trade-offs:** 决策更严，v3.0 失败的可能更高；但失败本身是 Core Value 的一部分（"证明 4B 已是甜点"也是合法结论）。

---

## Data Flow（v3.0 复用 v1.0 全部 artifact 链）

```
[REUSE]  reality.log → dist_prior.json → inputs.jsonl
[REUSE]  raw_responses/{sha256}.json
[REUSE]  data/labeled.jsonl                    ← v1.0 已有 ~2700+ valid
[REUSE]  data/splits/{train,val,ood_val}_idx.json (seed=42)

[REBUILD] data/tokenized/                       ← Qwen3.5 tokenizer
                  │
                  ▼  train.py (QLoRA r=64, bs=1×ga=32, eff=32, epoch=2)
[NEW]    runs/{v3_ts}/train/adapter/
                  │
                  ▼  parity_merge.py
[NEW]    runs/{v3_ts}/export/merged_fp16/
                  │
                  ▼  export_gguf.py
[NEW]    runs/{v3_ts}/export/model.fp16.gguf
[NEW]    runs/{v3_ts}/export/model.q4_K_M.gguf
                  │
                  ▼  run_eval.py
[NEW]    runs/{v3_ts}/eval/gen_cache/{variant}/
[REUSE]  runs/20260507T032419Z/eval/gen_cache/gguf_q4km/  ← v1.0 baseline
                  │
                  ▼  compute_metrics.py
[NEW]    runs/{v3_ts}/eval/per_sample.jsonl
[NEW]    runs/{v3_ts}/eval/report.md            ← 含 v3 vs v1 对比表 + ratio
[NEW]    runs/{v3_ts}/eval/decision.md          ← 三阈值 GO/NO-GO
```

---

## Build Order & Phase 拆分建议（v3.0）

### Dependency DAG

```
P0 tokenizer_check (Qwen3.5)  ──► P1 dataset_rebuild ──► P2 train ──► P3 export ──► P4 eval
                                       ▲                                              │
P0' env_dryrun (verify Qwen3.5 加载  ──┤                                              │
   + bnb 4-bit + SDPA on Spark)        │                                              │
                                       │                                              │
v1.0 labeled.jsonl + splits  ──────────┘                                              │
v1.0 runs/20260507T032419Z/gguf  ─────────────────────────────────────────────────────┘
```

### Phase 拆分（推荐 5 phases；每个 phase ≤ 1.5 天 / ≤ 6h GPU 预算）

| Phase | Goal | Depends on | Critical 退出条件 |
|-------|------|------------|---------------------|
| **Phase 1: Env + Tokenizer Sanity** | 在 `/home/samuel/dgx-spark-setup/.venv` 中 (a) `from transformers import Qwen3_5ForCausalLM` 成功；(b) `Qwen3.5-9B` config + tokenizer load 成功；(c) `tokenizer_check.py` 对 4 个自定义标签全部 multi-token，原生 `<think>` id 不冲突；(d) bnb 4-bit + SDPA + bf16 在 9B 模型上前向 1 step 不 OOM | nothing | `tokenizer_check` PASS；9B forward smoke OK |
| **Phase 2: Dataset Rebuild** | (a) `MODEL_NAME` 切 9B；(b) `dataset.py` 重跑，p99 + cap 重新落盘；(c) split seed=42 必须命中 v1.0 同集合（ood_val 哈希匹配） | Phase 1 | `data/tokenized/` 重建；split 哈希匹配 v1.0 |
| **Phase 3: QLoRA SFT (9B, bs=1)** | (a) target_modules 验证（Qwen3.5 GDN/MoE 路径下哪些线性层可挂 LoRA）；(b) 200-sample smoke run（30 min，确认 loss 下降、`</SOLUTION>` 出现）；(c) 全量 r=64 × 2 epoch 在 6h 预算内完成；(d) adapter 落盘 | Phase 1, 2 | smoke + 全量 SFT 完成；显存峰值 ≤ 100 GB |
| **Phase 4: Merge + GGUF Export** | (a) `merge_and_unload` → fp16 safetensors；(b) `convert_hf_to_gguf.py` 跑通（Qwen3_5ForCausalLM 路径）；(c) `llama-quantize Q4_K_M`；(d) parity 20-prompt：fp16 HF / fp16 GGUF / q4_K_M GGUF 三精度生成可读且含 SOLUTION | Phase 3 | model.q4_K_M.gguf 落盘；parity 三精度均生成合法 SOLUTION |
| **Phase 5: Eval Matrix + Decision** | (a) `run_eval.py` 跑 3 variant × 2 split = 6 run；(b) 拉 v1.0 baseline gen_cache 进 matrix；(c) `compute_metrics` 输出 ratio_vs_v1；(d) `decision.py` 三阈值评估 → `decision.md` GO/NO-GO | Phase 4 | report.md + decision.md 落地 |

**Build order rationale:**
- **Phase 1 必须在 dataset rebuild 之前**：tokenizer 验证失败时，整个 v3.0 假设需要回退（备选基座或回 4B），不能浪费 dataset rebuild 的 IO + 时间。
- **dataset rebuild 与 train 解耦**：让 train 阶段的 6h GPU 预算独立，不被 tokenize 占用。
- **export 单独 phase 而非 train 内联**：export 失败（Qwen3.5 GGUF 路径未工作过）需要独立调试；与训练耦合会让 6h 训练白跑。
- **eval 拆出来**：评测代码扩展（新 variant + ratio 指标）有自己的开发节奏；与训练日间分离。

**Critical path：Phase 3 是唯一的 6h GPU bottleneck；其他 phase 全部 ≤ 1h。**

### Phases NOT needed

- ~~"数据生成 phase"~~：v1.0 已 SHIPPED，labeled.jsonl 不重做（除非 Phase 1 发现 prompt 模板需为 Qwen3.5 调整 → 但这与基座无关，prompt 是协议层）。
- ~~"教师重标 phase"~~：教师固定 GPT-5.5 high，labeled.jsonl 复用。
- ~~"v2.0 标签协议迁移 phase"~~：v2.0 Phase 7 已完成，`prompt_builder.TAG_THINK_CLOSE = "<end_working_out>"` 已锁死，v3.0 直接继承，无需 reapply（grep 守门已通过 28 测试，见 `v2.0-abandoned/phases/07/07-01-SUMMARY.md`）。

---

## v1.0 资产复用清单（明确路径）

| 资产 | 路径 | v3.0 用法 |
|------|------|-----------|
| 教师标签数据 | `data/labeled.jsonl` | dataset rebuild 输入；不重生成 |
| Split 索引 (seed=42) | `data/splits/*_idx.json`（v1.0 Phase 4 产物） | dataset rebuild 必须复用同 seed/同 split，否则 v3 vs v1 不可比 |
| Prompt builder 协议 | `tsc_cycle/prompt_builder.py` | 直接 import，不动 |
| Phase 7 标签迁移 | `prompt_builder.TAG_THINK_CLOSE = "<end_working_out>"` + parser 旧标签拒绝分支 | 直接继承（v2.0 abandoned 但此组件经审已与 v3.0 兼容，见 PROJECT.md 第 56-58 行） |
| 教师 client | `tsc_cycle/teacher/client.py` | 仅备份用；本里程碑不调用 |
| 训练入口 | `tsc_cycle/student/train.py` | 改 MODEL_NAME 常量 + CLI 默认；其他不动 |
| Tokenize sanity | `tsc_cycle/student/tokenize_sanity.py` | import prompt_builder 常量自动随动；只需新基座下重跑 1 次 |
| Merge / parity / export | `tsc_cycle/student/{parity_merge,export_gguf,parity_*}.py` | 全部直接复用 |
| 评测 backbone | `tsc_cycle/eval/{run_eval,compute_metrics,decision}.py` | run_eval 加 variant；compute_metrics 加 ratio 列；decision 加阈值 |
| **v1.0 GGUF baseline artifact** | `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (2.4 GB) | v3.0 evaluator 第 4 个 variant；read-only |
| **v1.0 eval gen_cache** | `runs/20260507T032419Z/eval/gen_cache/gguf_q4km/` | 直接 mount-read，不重跑生成 |
| **v1.0 评测报告** | `runs/20260507T032419Z/eval/report.md`, `decision.md` | 决策对照锚点（98.7% / 99.3% / ratio=0.9933 / MAE Δ +0.18s） |
| llama.cpp 工具链 | `/home/samuel/projects/EvoProgTSC/llama.cpp/{convert_hf_to_gguf.py,llama-quantize}` | export 阶段直接子进程调用；**已确认 Qwen3_5ForCausalLM 注册在 line 5036** |

---

## llama.cpp Qwen3.5 支持核实（HIGH 证据）

**结论：本机 llama.cpp 已支持 Qwen3.5；v1.0 export pipeline 直接复用，零代码改动。无 fallback 需要。**

### 验证证据

```
$ grep -n "Qwen3_5" /home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py
4747: @ModelBase.register("Qwen3VLForConditionalGeneration", "Qwen3VLMoeForConditionalGeneration",
                          "Qwen3_5ForConditionalGeneration", "Qwen3_5MoeForConditionalGeneration")
5036: @ModelBase.register("Qwen3_5ForConditionalGeneration", "Qwen3_5ForCausalLM")
5037:  class Qwen3_5TextModel(_LinearAttentionVReorderBase):
5038:      model_arch = gguf.MODEL_ARCH.QWEN35
5041: @ModelBase.register("Qwen3_5ForConditionalGeneration", "Qwen3_5MoeForCausalLM")
5042:  class Qwen3_5MoeTextModel(_LinearAttentionVReorderBase):
5043:      model_arch = gguf.MODEL_ARCH.QWEN35MOE
```

- `Qwen3_5ForCausalLM`（HF Qwen3.5-9B 的 architecture string，**HIGH 信心** — 来自 HF model card 和 transformers 文档）已在 `Qwen3_5TextModel` 类注册（line 5036）。
- 父类 `_LinearAttentionVReorderBase`（line 4959）专门处理 Qwen3.5 的 Gated Delta Networks 线性注意力的 V-head 重排，说明 Qwen3.5 的 GDN 架构已被 llama.cpp 正确支持。
- `gguf.MODEL_ARCH.QWEN35` 枚举存在 → `llama-quantize` 能识别该架构跑 Q4_K_M。

### Fallback 路径（防御性，预期不需要）

如 Phase 4 export 阶段意外失败：
1. **首选**：升级本机 llama.cpp 到当前 main（`git -C /home/samuel/projects/EvoProgTSC/llama.cpp pull`），rebuild。
2. **备选 1**：clone 一份独立 llama.cpp 到 `~/llama.cpp.v3` 用 main 分支，避免污染 EvoProgTSC build。
3. **备选 2**（保守）：退到 **Qwen3-8B-Base**（架构 = Qwen3，与 4B 同；llama.cpp 第 4551 行的 `Qwen3ForCausalLM` 已注册；规模介于 4B 与 9B 之间，可作里程碑「9B 不可行时的降级承诺」）。
4. **不推荐**：unsloth `unsloth_convert_hf_to_gguf.py` — Issue #3861 的 wrapper 风险，且本机已 build cuda 版 llama.cpp 是更稳路径。

### Tokenizer 写入 GGUF metadata（与 v1.0 一致的注意点）

- Qwen3.5 vocab=248320，比 Qwen3 (151936) 大 ~63%；GGUF metadata 体积稍涨，对量化产物大小无显著影响。
- 自定义思考标签（4 个）按 BPE 拆 sub-token，**不要 `add_tokens()` 注册到 vocab**（v1.0 已踩过坑，q4_K_M 后新 token embedding 质量崩塌）。
- 与 v1.0 同样：训练只在 prompt 文本里写标签，不动 vocab。

---

## Anti-Patterns (v3.0 特有)

### Anti-Pattern 1: 把 v1.0 labeled.jsonl 删了重新调 GPT-5.5

**What people do:** "新基座新数据更新鲜" → 重新跑 4-6h 教师标注。
**Why it's wrong:** (1) GPT-5.5 high 重复调有非零随机性，v3.0 vs v1.0 数字不再严格可比（"是基座好了还是数据好了"无法分离）；(2) 浪费 USD 与时间；(3) 引入新 lint 失败样本可能让 train set 大小变化，更难归因。
**Do this instead:** 锁死 `data/labeled.jsonl` + split seed=42；v3.0 只换基座这一个变量。

### Anti-Pattern 2: 把 batch_size 加大到 2 来"省时间"

**What people do:** "9B 看起来还能塞" → bs=2，grad_accum=16。
**Why it's wrong:** (1) 用户在 PROJECT.md 明确锁死 batch_size=1（Out of Scope 第 76 行）；(2) 9B + r=64 + seq 2048 + bf16 + reasoning 长度，bs=2 在 DGX Spark 100GB MemoryMax 内不一定稳，OOM 风险显著；(3) 浪费 Phase 1 的 forward smoke 验证。
**Do this instead:** bs=1 + grad_accum=32（保持 effective batch=32 与 v1.0 一致）；省时间靠 epochs=2 不动 + 6h 预算紧密 watchdog。

### Anti-Pattern 3: 评测时让 v3.0 和 v1.0 跑不同的 ood_val 集

**What people do:** v3.0 重新做 split → ood_val 集合不同 → 跨里程碑数字不可比。
**Why it's wrong:** Decision gate 第 2 阈值（`q4_v3 vs q4_v1 ratio ≥ 1.0`）需要严格同分布同样本对比，否则 ratio 含义漂移。
**Do this instead:** Phase 2 退出条件包含「split 哈希必须匹配 v1.0」；不过这要求 v1.0 split 索引文件 (`data/splits/*_idx.json`) 仍然在仓库 / runs/ 中（GSD 审计核实）。

### Anti-Pattern 4: 跳过 Phase 1 tokenizer_check 直接进训练

**What people do:** "v1.0 已验证，v3.0 一样" → 跳过 sanity gate。
**Why it's wrong:** Qwen3.5 是新 vocab（248320 vs 151936），且 thinking mode 默认开启 → `<think>` token 在 chat_template 中位置不同；自定义标签是否与新 vocab 中某子串冲突需要重新验证。MEMORY 已经记载 v2.0 阶段的标签语义冲突教训。
**Do this instead:** Phase 1 是硬门，5 秒检查保 6h 训练。

### Anti-Pattern 5: 把 v1.0 baseline 的 gen_cache 也重跑

**What people do:** "干净点重跑一遍" → 浪费 30 min × N variant。
**Why it's wrong:** v1.0 gen_cache 是确定性产物（temperature=0），重跑得到完全相同结果；新里程碑不是审计 v1.0 而是用它做对照。
**Do this instead:** evaluator 直接 read-only mount `runs/20260507T032419Z/eval/gen_cache/`；指标层重新计算即可（毫秒级）。

---

## Integration Points

### External Services（v1.0 不变）

| Service | Integration Pattern | v3.0 Notes |
|---------|---------------------|------------|
| OpenAI GPT-5.5 (teacher) | `tsc_cycle/teacher/client.py` 已封装 | **不调用**；labeled.jsonl 复用 |
| llama.cpp `convert_hf_to_gguf.py` | 子进程调用，传 merged_fp16 | Qwen3_5ForCausalLM 路径已注册（line 5036） |
| llama.cpp `llama-quantize` | 子进程，传入 fp16.gguf | 不变；Q4_K_M preset 15 |
| llama.cpp `llama-server` (CUDA) | eval 时调用 | 不变；v1.0 已切 CUDA build (`/home/samuel/llama.cpp/build/bin/llama-server`) |

### Internal Boundaries

| Boundary | v3.0 变化 |
|----------|-----------|
| dataset_builder ↔ trainer | tokenized arrow path 改名（`data/tokenized/v3/`），避免覆盖 v1.0 |
| trainer ↔ exporter | 不变 |
| exporter ↔ evaluator | evaluator 现在读两套 GGUF（v3 + v1 baseline） |
| 所有 stage ↔ runner | manifest 增加 `base_model: "Qwen/Qwen3.5-9B"` 字段 |

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **本里程碑：3000 样本，1 模型 (9B)，bs=1×ga=32** | 显存压力是首要瓶颈：r=64 + bnb 4-bit + bf16 + seq 2048 在 100GB MemoryMax 下应可（4B 是 ~30-40GB，9B 估 ~60-75GB；bs=1 给足 headroom） |
| 9B + 长 reasoning (seq>4096) | 触发 OOM 时降到 r=32 / `gradient_checkpointing=True` / 或退到 Qwen3-8B |
| 多 ckpt 对比（v3-r32 / v3-r64 / v3-r128） | 当前 `runs/{ts}/` 已支持；`tsc-cycle compare` 子命令可加但非本里程碑必需 |

### First Bottlenecks (v3.0 排序)

1. **Phase 3 训练显存**（最先卡）：9B 比 4B 增 2.25× 参数；bnb 4-bit 把 active 权重压到 ~5 GB，但 LoRA r=64 grad + activation + KV 长 reasoning 是大头。**冒烟 forward 1 step 必须在 Phase 1 做完**，不要等 Phase 3 才发现。
2. **Phase 4 export 时间**（次卡）：merge_and_unload 9B fp16 ~ 18GB safetensors → `convert_hf_to_gguf.py` 单线程 ~5-10 min；`llama-quantize Q4_K_M` 9B 估 ~10-15 min（4B 在 v1.0 是 ~3 min）。可接受，无需优化。
3. **Phase 5 eval 时间**：q4_K_M 9B 推理 ~2-3× 慢于 4B（latency 不是吞吐瓶颈，模型大小翻倍）；600 prompt 估 ~60-90 min。Cache 命中后指标重算秒级。

---

## Confidence Summary

| Recommendation | Confidence | Rationale |
|----------------|------------|-----------|
| llama.cpp 已支持 Qwen3_5ForCausalLM，零 fallback | **HIGH** | 本机文件 line 5036 直接证据；`MODEL_ARCH.QWEN35` 枚举存在；GDN 父类专门处理 V-head 重排 |
| 教师 labeled.jsonl 跨基座可复用 | **HIGH** | 教师固定 GPT-5.5 high；prompt 协议（Phase 7 锁定）与基座无关；硬约束 lint 已 SHIPPED 验证 |
| Phase 7 标签迁移产物可直接继承到 v3.0 | **HIGH** | v2.0 abandoned 但 Phase 7 是协议层修正（与基座无关）；PROJECT.md 第 56-58 行明示沿用；29 测试 PASS |
| bs=1 + grad_accum=32 在 6h 预算内可完成 9B SFT | **MEDIUM** | 4B + bs=4×ga=8 在 v1.0 是 ~3-4h；9B 计算量 2.25×，bs 减 4× 互相抵消，理论 ~3-5h；但 GDN 架构没有 v1.0 实测，需 Phase 1 forward smoke + Phase 3 200-sample dry-run 兜底 |
| Qwen3.5 tokenizer 不会与自定义标签冲突 | **MEDIUM** | Qwen3.5 vocab 248320（远大于 Qwen3 151936），合并新词更多但通常 BPE 不会把 `<start_working_out>` 这种结构合成单 token；MEMORY 仅验证过 Qwen3，**Qwen3.5 必须 Phase 1 重新验证** |
| target_modules `[q,k,v,o,gate,up,down]_proj` 适用 Qwen3.5 GDN 层 | **MEDIUM** | Qwen3.5 主体仍是 Transformer，但 GDN 引入 conv1d / delta gate 等新参数；这些层名不在标准 LoRA target 列表；**Phase 3 必须 print model 验证哪些 nn.Linear 名匹配**，必要时扩展 target_modules |
| v1.0 q4_K_M GGUF 仍可加载到当前 llama-server | **HIGH** | v1.0 SHIPPED 时已验证；GGUF 格式向后兼容；artifact 文件未删（PROJECT.md 第 21 行确认） |
| v1.0 split 索引仍在仓库 | **MEDIUM** | v1.0 ROADMAP 标记 Phase 4 完成；但 git status 显示 `data/labeled.jsonl.bak`（说明数据有过手工调整）；Phase 2 退出门必须显式校验 split 哈希 |

---

## Sources

- [Qwen/Qwen3.5-9B HF model card](https://huggingface.co/Qwen/Qwen3.5-9B) — HIGH（确认模型存在；vocab 248320；thinking mode 默认开；context 262K；最新 transformers 必需）
- [Transformers Qwen3.5 docs](https://huggingface.co/docs/transformers/model_doc/qwen3_5) — HIGH（`Qwen3_5ForCausalLM` 类正式注册，5.2.0+ 起；本机 venv 已 5.8.0）
- [vLLM Issue #39993 — Qwen3_5ForCausalLM support](https://github.com/vllm-project/vllm/issues/39993) — MEDIUM（旁证：HF transformers 是当前最稳路径；v3.0 不需要 vLLM 反而是优势）
- 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py:5036` — HIGH（`Qwen3_5ForCausalLM` 已注册；直接 grep 验证）
- 本机 `/home/samuel/dgx-spark-setup/.venv/lib/python*/site-packages/transformers-5.8.0.dist-info` — HIGH（已满足 ≥5.2.0 要求）
- v1.0 SHIPPED milestone: `.planning/milestones/v1.0-ROADMAP.md` — HIGH（Phase 1-6 闭环；q4_K_M ratio=0.9933；artifact 路径 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf`）
- v2.0 abandoned: `.planning/milestones/v2.0-abandoned/phases/07/07-01-SUMMARY.md` — HIGH（标签迁移已完成；29 测试 PASS；与 v3.0 兼容声明） 
- v2.0 abandoned ARCHITECTURE: `.planning/milestones/v2.0-abandoned/research/ARCHITECTURE.md` — HIGH（v1.0 时代的完整架构 baseline，本文档增量基础）
- PROJECT.md (TSC-CYCLE) 第 27-77 行 — HIGH（v3.0 milestone goals + Out of Scope 锁死 batch=1 + 不引入新栈）
- DGX Spark 训练栈约束: `/dgx-spark-training` skill；本机 `/home/samuel/dgx-spark-setup/.venv` — HIGH（venv 复用，环境锁定）

---
*Architecture research for: TSC-CYCLE v3.0 9B 基座切换（蒸馏 pipeline 增量改造）*
*Researched: 2026-05-08*
