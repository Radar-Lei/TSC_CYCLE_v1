# Architecture Research

**Domain:** LLM 蒸馏离线批处理流水线（合成数据 → 教师 API 标注 → QLoRA SFT → GGUF 导出 → 评测）
**Researched:** 2026-05-07
**Confidence:** HIGH（流水线结构清晰、单机离线、无服务化复杂度；teacher API 重试/缓存策略经过 EvoProgTSC 实战验证）

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 1: SAMPLER (offline, CPU, < 5 min)                                    │
│    reality.log ──► distribution_fit.py ──► dist_prior.json                   │
│    dist_prior.json ──► sample_inputs.py  ──► inputs.jsonl  (3000 records)   │
│                                              │                               │
│                                              │  + ood_inputs.jsonl (300)     │
└──────────────────────────────────────────────┼───────────────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 2: TEACHER LABELER (network-bound, 4-6h, ≤10 worker)                  │
│                                                                              │
│    inputs.jsonl ──► prompt_builder ──► OpenAI client ──► raw_responses/      │
│                                          │ (concurrent)    {hash}.json       │
│                                          │                                   │
│                                          ▼                                   │
│                                    constraint_lint  ──► labeled.jsonl        │
│                                          │                rejected.jsonl     │
│                                          │                resume_index.json  │
└──────────────────────────────────────────┼──────────────────────────────────┘
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 3: DATASET BUILDER (CPU, < 10 min)                                    │
│    labeled.jsonl ──► split (80/10/10) ──► train.jsonl / val.jsonl /          │
│                                          ood_val.jsonl                       │
│    + tokenize ──► HF Dataset on disk (arrow) under data/tokenized/           │
└──────────────────────────────────────────┼──────────────────────────────────┘
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 4: TRAINER (GPU, ≤ 6h on DGX Spark GB10)                              │
│    HF Dataset ──► QLoRA r=64 SFT (transformers + PEFT or Unsloth)            │
│              ──► runs/{ts}/checkpoints/   (every N steps, resumable)         │
│              ──► runs/{ts}/adapter/       (final LoRA)                       │
│              ──► runs/{ts}/train_log.jsonl                                   │
└──────────────────────────────────────────┼──────────────────────────────────┘
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 5: EXPORTER (CPU + small GPU, ~30 min)                                │
│    adapter/ ──► merge_lora.py ──► merged_fp16/  (HF safetensors)             │
│             ──► convert_hf_to_gguf.py ──► model.fp16.gguf                    │
│             ──► llama-quantize ──► model.q4_K_M.gguf                         │
└──────────────────────────────────────────┼──────────────────────────────────┘
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Stage 6: EVALUATOR (GPU + llama.cpp CPU/GPU, ≤ 1h)                          │
│    val.jsonl + ood_val.jsonl                                                 │
│      ──► generate (HF fp16, llama.cpp fp16, llama.cpp q4_K_M)                │
│      ──► gen_cache/{variant}/{hash}.json   (cached, idempotent)              │
│      ──► metrics: hard_constraint_pass / MAE_vs_teacher /                    │
│                   ood_gap / reasoning_keyword_recall                          │
│      ──► reports/{ts}/report.md  +  reports/{ts}/per_sample.jsonl            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| **distribution_fit** | 解析 `reality.log`，统计相位数 / min_green / max_green / capacity / pred_wait / pred_saturation 的边缘分布与组合先验 | 纯 Python，正则 + pandas；输出 `dist_prior.json` |
| **sample_inputs** | 按 `dist_prior.json` 采样 in-distribution 输入；按显式 OOD 规则（拉宽 min/max、增多相位、极端 saturation）生成 OOD 输入 | numpy + 显式规则；可重复（seed 写入 record） |
| **prompt_builder** | 把输入参数渲染为 reality.log 协议的 prompt（含硬约束说明、`<start_working_out>`/`<SOLUTION>` 标签要求） | 单文件模板；输入是 dict，输出是 str；与 SFT/eval 共用 |
| **teacher_client** | 并发调用 GPT-5.5 high；重试 / 退避 / 速率限制 / response 缓存 | 复用 `EvoProgTSC/llm/client.py` 模式；hash-by-input 落盘 `raw_responses/{sha256(prompt)}.json` |
| **constraint_lint** | 解析教师响应；提取 `<SOLUTION>` JSON；硬约束校验（min/max、整数、相位完整、顺序）；rejection bucket | 纯 Python；输出 `labeled.jsonl` + `rejected.jsonl` + 统计 |
| **dataset_builder** | 80/10/10 划分（OOD 单列）；用学生 tokenizer tokenize；保存 arrow | datasets 库；保存到 `data/tokenized/` |
| **trainer** | QLoRA r=64 SFT，2+ epochs；checkpoint；resume；只在 `<start_working_out>` 之后计算 loss（可选：mask prompt） | transformers + PEFT 或 Unsloth；TrainingArguments resume_from_checkpoint |
| **exporter** | merge LoRA 到基座 fp16 → 转 GGUF fp16 → quantize q4_K_M | PEFT `merge_and_unload()` + llama.cpp 脚本（已 build 在 EvoProgTSC） |
| **evaluator** | 三个 variant（HF fp16 / GGUF fp16 / GGUF q4_K_M）跑 val + ood_val；生成结果落盘缓存；指标计算与对比报告 | HF generate + llama-cli/llama-server；指标层与生成层解耦 |
| **runner / cli** | 顶层入口，编排 stage、读统一 config、写 run manifest | 单一 CLI（`tsc-cycle <stage>`）+ 子命令 |

---

## Recommended Project Structure

```
TSC_CYCLE/
├── pyproject.toml                  # 单一 package，src layout
├── README.md
├── reality.log                     # 输入参数分布先验来源（已有）
├── .planning/                      # GSD 规划（已有）
│   ├── PROJECT.md
│   └── research/
│
├── configs/
│   ├── default.yaml                # 全栈默认配置
│   ├── data.yaml                   # 数据生成 / 教师标注子配置
│   ├── train.yaml                  # SFT 子配置（LoRA rank, epochs, lr, …）
│   └── eval.yaml                   # 评测子配置
│
├── src/tsc_cycle/
│   ├── __init__.py
│   ├── cli.py                      # 顶层入口：`tsc-cycle {sample|label|build|train|export|eval|all}`
│   ├── config.py                   # pydantic Settings；加载/合并 YAML + CLI 覆盖
│   ├── io_paths.py                 # 集中管理所有产物路径（runs/{ts}/...）
│   │
│   ├── data/
│   │   ├── distribution_fit.py     # reality.log → dist_prior.json
│   │   ├── sample_inputs.py        # dist_prior + OOD 规则 → inputs.jsonl
│   │   ├── prompt_builder.py       # 输入 dict → prompt str（与 reality.log 协议一致）
│   │   ├── constraint_lint.py      # 教师输出校验 + 解析
│   │   └── dataset_builder.py      # split + tokenize → HF Dataset
│   │
│   ├── teacher/
│   │   ├── client.py               # OpenAI client 封装（复用 EvoProgTSC 模式）
│   │   ├── label.py                # 并发 orchestrator（≤10 worker）+ resume 逻辑
│   │   └── cache.py                # 内容寻址缓存（sha256(prompt) → response file）
│   │
│   ├── train/
│   │   ├── train.py                # SFT 主循环；transformers Trainer 或 Unsloth
│   │   ├── data_collator.py        # prompt-mask collator（可选）
│   │   └── tokenizer_check.py      # 启动时验证自定义标签被拆 sub-token、且不命中 151667/151668
│   │
│   ├── export/
│   │   ├── merge.py                # PEFT merge_and_unload → fp16 safetensors
│   │   └── to_gguf.py              # 包装 llama.cpp convert + quantize
│   │
│   ├── eval/
│   │   ├── runners/
│   │   │   ├── hf_fp16.py
│   │   │   ├── gguf_fp16.py        # llama-cli / llama-server 客户端
│   │   │   └── gguf_q4km.py
│   │   ├── metrics.py              # hard_constraint_pass / MAE / OOD gap / keyword recall
│   │   ├── gen_cache.py            # 生成结果缓存（按 variant + sample hash）
│   │   └── report.py               # 汇总报告 markdown
│   │
│   └── utils/
│       ├── logging.py
│       ├── hashing.py
│       └── manifest.py             # run manifest 写入与读取
│
├── runs/                           # 所有运行产物（gitignored）
│   └── {YYYYMMDD-HHMM}/
│       ├── manifest.json           # 配置 hash + git sha + 阶段状态
│       ├── data/
│       │   ├── dist_prior.json
│       │   ├── inputs.jsonl
│       │   ├── ood_inputs.jsonl
│       │   ├── raw_responses/      # {sha256}.json（教师原始输出，缓存基石）
│       │   ├── labeled.jsonl
│       │   ├── rejected.jsonl
│       │   ├── resume_index.json   # 已成功标注的 input_id 集合
│       │   └── tokenized/          # arrow dataset
│       ├── train/
│       │   ├── checkpoints/        # HF Trainer 标准 checkpoint
│       │   ├── adapter/            # 最终 LoRA
│       │   └── train_log.jsonl
│       ├── export/
│       │   ├── merged_fp16/        # HF safetensors
│       │   ├── model.fp16.gguf
│       │   └── model.q4_K_M.gguf
│       └── eval/
│           ├── gen_cache/{variant}/{sample_hash}.json
│           ├── per_sample.jsonl
│           └── report.md
│
└── tests/
    ├── test_constraint_lint.py     # 关键：校验逻辑必须有单测
    ├── test_prompt_builder.py
    ├── test_tokenizer_check.py     # 防止 Qwen3 tokenizer 词表回归
    └── test_metrics.py
```

### Structure Rationale

- **src layout + 单包**：流水线虽然 6 个 stage，但只有一个部署单元（一台 DGX Spark），分多个 package 反而徒增 import 与测试复杂度。
- **`prompt_builder.py` 单文件全局共用**：训练输入、教师标注、评测推理三处用同一个 prompt 渲染器是不可让步的——任何不一致都会让 metric 含义漂移。
- **`runs/{timestamp}/` 总目录**：所有可重跑产物统一放一个时间戳子目录，便于 `--resume runs/2026-05-07-1830/` 一键续跑、对比、归档。`manifest.json` 记录 config hash + git sha 是 reproducibility 锚点。
- **`raw_responses/` 内容寻址（sha256(prompt)）**：教师 API 是流水线最贵的一段（USD + 时间），缓存层独立于业务逻辑，构建在文件系统而非 sqlite——单文件 corruption 不会拖垮整体；并发安全由 atomic rename 保证。
- **`eval/runners/` 三 runner 并列**：`hf_fp16` / `gguf_fp16` / `gguf_q4km` 实现完全解耦，是因为它们的执行路径完全不同（python in-process vs. 子进程 llama-cli）。共享只需一个 `Generation` dataclass。
- **`tests/` 集中放硬约束 lint 与 tokenizer 检查**：这两个组件错了会污染整批训练数据 / 训练崩溃，必须有红绿测试。

---

## Architectural Patterns

### Pattern 1: Stage = Pure Function over (Config, InputArtifacts) → OutputArtifacts

**What:** 每个 stage 严格只读上游产物 + config，写自己产物，不持有跨 stage 状态。
**When to use:** 离线批处理流水线的标配；让每个 stage 独立可重跑。
**Trade-offs:** 略多磁盘 IO，但获得 idempotency + 易调试。

**Example:**
```python
# src/tsc_cycle/teacher/label.py
def run_label(cfg: TeacherCfg, inputs_path: Path, out_dir: Path) -> LabelResult:
    cache = ResponseCache(out_dir / "raw_responses")
    todo = load_inputs(inputs_path) - cache.completed_ids()  # resume diff
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as ex:
        for resp in ex.map(lambda x: call_with_retry(x, cache), todo):
            ...
    return write_labeled_jsonl(cache, out_dir / "labeled.jsonl")
```

### Pattern 2: Content-Addressed Cache for Expensive Side-Effects

**What:** 用 `sha256(prompt + model + reasoning_effort)` 作为 cache key，落盘 `raw_responses/{key}.json`。
**When to use:** 任何重跑成本远高于磁盘成本的外部调用（教师 API、评测生成）。
**Trade-offs:** 需要严谨的 prompt 规范化（去空白、确定 JSON key 顺序），否则 cache miss 率虚高。

**Example:**
```python
def cache_key(prompt: str, model: str, reasoning_effort: str) -> str:
    payload = json.dumps({"p": prompt, "m": model, "r": reasoning_effort},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()
```

### Pattern 3: Run Manifest as Single Source of Truth

**What:** `runs/{ts}/manifest.json` 记录 config 哈希、git sha、每个 stage 的 status/start/end/产物路径。
**When to use:** 需要回答「这个 GGUF 是用哪份数据 / 哪次 commit / 哪份 config 训出来的」。
**Trade-offs:** 多一份元数据维护；但是定位「哪次实验产生了这个数字」时不可或缺。

### Pattern 4: Tokenizer Sanity Gate at Train Boot

**What:** 训练入口第一步运行 `tokenizer_check.py`，断言自定义思考标签被拆为多个普通 sub-token、且 `<think>`/`</think>` 的 token id（151667/151668）不出现在训练数据中。
**When to use:** Qwen3 系列学生模型 + 自定义 reasoning 标签的所有项目（项目 memory 已记录此教训）。
**Trade-offs:** 多 5 秒启动；但避免 6h 训练后才发现学到乱码。

### Pattern 5: Three-Variant Eval Matrix with Shared Generation Cache

**What:** 评测把 `(variant, sample) → generation` 写入 `gen_cache/`；指标计算只读缓存。
**When to use:** 多 variant（fp16 / q4_K_M / 不同 ckpt）需要在同一份 val/ood 上对比。
**Trade-offs:** 指标改进可瞬时重算；但首次生成仍需跑完一遍。

---

## Data Flow

### End-to-End Artifact Chain

```
reality.log
   │
   ▼  distribution_fit
dist_prior.json                             {"phases": {...}, "ranges": {...}}
   │
   ▼  sample_inputs (+ OOD rules)
inputs.jsonl       ←  {"id":"in_0001","seed":42,"phase_waits":[...]}
ood_inputs.jsonl
   │
   ▼  prompt_builder + teacher_client (concurrent, cached)
raw_responses/{sha256}.json                 OpenAI 完整响应 + token usage
   │
   ▼  constraint_lint
labeled.jsonl      ←  {"id":"in_0001","prompt":"...","completion":"<start_working_out>...</end_working_out><SOLUTION>{...}</SOLUTION>","teacher_solution":{...},"input":{...}}
rejected.jsonl     ←  {"id":"...","reason":"min_green_violation","raw":"..."}
   │
   ▼  dataset_builder (split 80/10/10, OOD 单列)
data/tokenized/    ←  HF arrow dataset，列：input_ids, labels（prompt 部分 mask=-100）
   │
   ▼  trainer (QLoRA r=64, 2 epochs)
runs/{ts}/train/checkpoints/checkpoint-{step}/   每 N step
runs/{ts}/train/adapter/                          最终 LoRA 权重 + tokenizer 副本
   │
   ▼  exporter
runs/{ts}/export/merged_fp16/                     safetensors + config.json + tokenizer
runs/{ts}/export/model.fp16.gguf
runs/{ts}/export/model.q4_K_M.gguf
   │
   ▼  evaluator (3 variants × 2 split = 6 runs)
runs/{ts}/eval/gen_cache/{variant}/{sample_hash}.json
runs/{ts}/eval/per_sample.jsonl                   指标逐样本
runs/{ts}/eval/report.md                          汇总（pass_rate, MAE, OOD_gap）
```

### File Format Specifications

**`inputs.jsonl`** (one record per line):
```json
{"id": "in_0001", "seed": 42, "ood": false,
 "phase_waits": [{"phase_id":1,"pred_wait":0.4,"pred_saturation":0.0083,"min_green":50,"max_green":80,"capacity":48}, ...]}
```

**`labeled.jsonl`** (one record per line):
```json
{"id": "in_0001",
 "input": {...同上 phase_waits...},
 "prompt": "你是交通信号配时优化专家。...",
 "completion": "<start_working_out>先保持原始相位顺序...</end_working_out><SOLUTION>{\"1\":50,\"2\":20,\"3\":45,\"4\":20}</SOLUTION>",
 "teacher_solution": {"1":50,"2":20,"3":45,"4":20},
 "teacher_meta": {"model":"gpt-5.5","reasoning_effort":"high","tokens_in":712,"tokens_out":340},
 "lint": {"hard_constraints_pass": true}}
```

**`raw_responses/{sha256}.json`**:
```json
{"key":"abc123...","prompt_hash":"...","model":"gpt-5.5","reasoning_effort":"high",
 "request":{...},"response":{...openai raw chat.completion...},
 "received_at":"2026-05-07T18:30:11Z","attempt":1}
```

**`runs/{ts}/manifest.json`**:
```json
{"run_id":"2026-05-07-1830","git_sha":"abc...","config_hash":"...",
 "stages":{"sample":{"status":"done","artifacts":[...],"started":"...","ended":"..."},
            "label":{"status":"in_progress","completed":2174,"total":3300}, ...}}
```

---

## Build Order & Critical Path

### Dependency DAG

```
P1 distribution_fit  ─┐
                      ├─► P2 sample_inputs ─► P3 teacher_label ─► P4 dataset_builder ─► P5 train ─► P6 export ─► P7 eval
P0 prompt_builder ────┤                            ▲
                      │                            │
P0' constraint_lint ──┘                            │ (used inline)
                                                   │
P0'' tokenizer_check ──────────────────────────────┘ (and at train boot)
```

### Recommended Phase Order

1. **Phase A — Foundations (parallel-friendly, day 1)**
   - `prompt_builder` + golden test against reality.log
   - `constraint_lint` + unit tests on rejected/accepted samples
   - `tokenizer_check` script
   - `distribution_fit` on reality.log → `dist_prior.json` 落地
   - `teacher_client` 用 EvoProgTSC 现成代码，**先用 5-10 个样本端到端打通**（节流验证）

2. **Phase B — Data Pipeline (day 2-3)**
   - `sample_inputs` + OOD 规则
   - 全量 3000 样本教师标注（**4-6h 异步执行**；可在 Phase A 末就启动后台跑）
   - `dataset_builder` split + tokenize

3. **Phase C — Training (day 3-4, 单次 ≤6h)**
   - QLoRA SFT 主循环；先小规模（200 样本）冒烟，再上全量
   - **关键：第一次全量训练前，已有 dataset 就绪，否则 6h 预算会因等数据而打折**

4. **Phase D — Export & Eval (day 4-5)**
   - merge → GGUF fp16 → q4_K_M（顺序，~30min）
   - 三 variant eval

### Critical Path for 6h Training Budget

```
T-24h: 启动教师标注后台进程（最长一段）
T-6h:  确认 labeled.jsonl 数量 ≥ 2400 可接受样本（reject 率 ≤ 20%）
T-5h:  dataset_builder 跑完（≤10 min）
T-5h:  小规模冒烟训练 200 样本 × 1 epoch（≤30 min，验证 loss 下降、梯度无 NaN、eval 输出含合法 SOLUTION）
T-4.5h:启动全量 QLoRA r=64 × 2 epoch（预算 4h，留 30min 余量）
T-0.5h:训练完成；merge+GGUF（30 min）
后续:   eval（独立计时，不算训练 6h 内）
```

**Parallelizable work**（不阻塞训练 6h）：
- Phase A 全部 component 可与教师标注并行开发
- Eval runners 可在训练运行期间预先实现并用旧 ckpt 联调

**Critical hazards 对 6h 预算**：
- DGX Spark GB10 aarch64 无 flash-attn cu12 wheel → SDPA 慢 ~15-20% → batch/grad-accum 必须先实测
- QLoRA r=64 + 4B 模型 + seq 长（含 reasoning）显存压力大；**冒烟阶段必须确认 max_seq_length 与 batch size 不会触发 OOM/swap**

---

## Stage Idempotency / Resumability

| Stage | 重跑代价 | 缓存粒度 | Resume 机制 |
|-------|----------|----------|-------------|
| distribution_fit | 秒级 | 不缓存（直接覆盖） | 输入变即重跑 |
| sample_inputs | 秒级 | 通过 seed 确定性 | seed 写入 record；同 seed = 同输出 |
| **teacher_label** ⚠ | **4-6h + USD** | **per-prompt sha256，文件系统** | **启动时 diff `cache.completed_ids() - inputs.ids`，只补缺失；中断不丢已完成；并发用 atomic write（写 .tmp → rename）** |
| constraint_lint | 秒级 | 不缓存 | 直接对 raw_responses/ 重跑 |
| dataset_builder | < 10 min | datasets `save_to_disk` | tokenized/ 存在即跳过；config 变即触发重建（manifest 比对 config_hash） |
| train | ≤ 6h | HF Trainer checkpoints 每 N step | `--resume_from_checkpoint runs/{ts}/train/checkpoints/checkpoint-XXXX`；需带相同 dataset 与 config |
| export merge | 几分钟 | 文件存在性 | merged_fp16/ 已存在则跳过；GGUF 同理 |
| eval | < 1h | **每 (variant, sample_hash) 一个 json** | `gen_cache/` 命中即不重生成；只重算指标即可秒级出新报告 |

### Teacher Labeling — 详细 Resume 流程

1. 启动时扫描 `raw_responses/`，构建 `completed_keys = {load(f).key for f in dir}`。
2. 对每个 input record 计算 `key = sha256(canonical_prompt + model + effort)`。
3. `todo = [r for r in inputs if key(r) not in completed_keys]`。
4. 并发执行 `todo`，单条流程：`call API → write tmp file → rename to {key}.json → update progress bar`。
5. 全部 raw 收齐后，单线程跑 `constraint_lint` 生成 `labeled.jsonl`（lint 是纯函数，可任意重跑）。
6. **关键不变量**：`raw_responses/` 是 source of truth；`labeled.jsonl` 是它的 derived view。删除 `labeled.jsonl` 不会丢钱。

### Eval — Re-run Cheap

- 加新指标：只重跑 `metrics.py`（毫秒级），不重生成。
- 加新 variant：只跑该 variant 的 generate，老 variant 缓存复用。
- 改 prompt：缓存全部失效（因为 sample_hash 含 prompt），但这是预期行为。

---

## Configuration Surface

**结论：单文件 `configs/default.yaml` 为主，子配置可按 stage 拆分但必须可被默认配置 include。** 所有 stage 共享同一个 pydantic root model，避免「数据生成用了 reasoning_effort=high，eval 评比时用了 medium」之类的偷换。

### 必须暴露的 Knobs

```yaml
# configs/default.yaml
data:
  reality_log_path: "./reality.log"
  total_samples: 3000
  ood_ratio: 0.10              # 10% OOD val（独立生成而非 split）
  seed: 42

teacher:
  model: "gpt-5.5"
  reasoning_effort: "high"
  max_workers: 10
  retry:
    max_attempts: 5
    base_backoff_s: 2.0
  request_timeout_s: 180

dataset:
  split: {train: 0.8, val: 0.1, ood_val: 0.1}
  max_seq_length: 2048
  prompt_loss_mask: true       # 只对 completion 计算 loss

train:
  base_model: "Qwen/Qwen3-4B-Thinking-2507"
  lora:
    r: 64
    alpha: 128
    target_modules: ["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]
  num_train_epochs: 2          # memory: 1 epoch 不够
  per_device_batch_size: 2
  gradient_accumulation_steps: 8
  learning_rate: 2.0e-4
  bf16: true                   # GB10 支持
  attn_implementation: "sdpa"  # 禁用 flash-attn cu12
  save_steps: 100
  eval_steps: 200

export:
  llama_cpp_dir: "/home/samuel/projects/EvoProgTSC/llama.cpp"
  quant_variants: ["q4_K_M"]   # fp16 默认产出，q4_K_M 列表

eval:
  variants: ["hf_fp16", "gguf_fp16", "gguf_q4km"]
  generation:
    max_new_tokens: 1024
    temperature: 0.0           # deterministic for metric stability
  metrics: ["hard_constraint_pass", "mae_vs_teacher", "ood_gap", "reasoning_keyword_recall"]
```

### CLI 覆盖（最高优先级）

```bash
tsc-cycle train --config configs/default.yaml --train.lora.r 32 --train.num_train_epochs 3
```

---

## CLI / Entry-Point Design

**结论：单一统一 CLI（`tsc-cycle`）+ stage 子命令。** 而不是 7 个独立脚本。

### Rationale

- **统一 config 加载**：每个子命令都共用 `config.py`，避免「这个脚本用 yaml，那个脚本用 argparse」的不一致。
- **统一 run manifest 写入**：每次调用自动 append 到 `runs/{ts}/manifest.json`，全局可观测。
- **`tsc-cycle all`**：端到端跑通，新人 onboarding 一行命令。

### Subcommands

```bash
tsc-cycle fit-dist        --config configs/default.yaml [--run-id 2026-05-07-1830]
tsc-cycle sample          --run-id ...
tsc-cycle label           --run-id ... [--resume]
tsc-cycle build-dataset   --run-id ...
tsc-cycle train           --run-id ... [--resume]
tsc-cycle export          --run-id ... [--variants q4_K_M]
tsc-cycle eval            --run-id ... [--variants hf_fp16,gguf_q4km] [--samples val,ood_val]
tsc-cycle all             --config configs/default.yaml         # 编排上述全部
tsc-cycle inspect         --run-id ...                          # 打印 manifest 摘要
```

`--run-id` 缺省时自动生成 `YYYYMMDD-HHMM`；继续已有 run 则显式传。`--resume` 在 label/train 上启用 stage 级别 resume 逻辑。

### Anti-pattern 避坑

- **不要**写成 `python -m tsc_cycle.train.train`：模块路径暴露增加重构成本；CLI 子命令是稳定接口。
- **不要**为每个 stage 写独立 `argparse`：必然走向不一致。

---

## Anti-Patterns

### Anti-Pattern 1: 把 prompt 渲染逻辑分散到 train/teacher/eval 三处

**What people do:** 训练 collator 里硬编码一份 prompt 模板，教师标注里又写一份，eval 里又写一份。
**Why it's wrong:** 三份必然漂移；某次"小修"会让某 metric 突然变好/变差，根因调查极难。
**Do this instead:** `prompt_builder.py` 单一来源；三处都 `from tsc_cycle.data.prompt_builder import build_prompt`。

### Anti-Pattern 2: 把教师 API 缓存做进 sqlite

**What people do:** 用 sqlite 记录 `(prompt_hash → response)`。
**Why it's wrong:** 并发 writer 容易锁；单条 corruption 影响全表；调试时 `cat` 不出来。
**Do this instead:** 一个 prompt 一个 json 文件，文件名即 hash；并发安全靠 atomic rename。

### Anti-Pattern 3: 训练数据集合直接保留在 jsonl，每次训练即时 tokenize

**What people do:** Dataset.from_json + map(tokenize) 每次训练时跑一遍。
**Why it's wrong:** Qwen3 tokenizer 跑 3000 样本带 reasoning 不便宜；多次实验重复浪费；且 tokenizer 改动可能悄悄改变训练分布。
**Do this instead:** `dataset_builder` 一次性 tokenize 落 arrow，trainer 直接 `load_from_disk`。tokenizer 哈希写进 manifest。

### Anti-Pattern 4: 用模型原生 `<think>` 做 SFT 标签

**What people do:** 直接复用 Qwen3 的 `<think>...</think>` 包裹 reasoning。
**Why it's wrong:** 词表中的 added token id (151667/151668) 已带预训练语义，自定义 SFT 会冲突，模型学不出干净 `</think>`。
**Do this instead:** 沿用 reality.log 体系的 `<start_working_out>/<end_working_out>/<SOLUTION>/</SOLUTION>`——它们被拆成多个 sub-token，无冲突。**`tokenizer_check.py` 在每次训练入口必须 assert 这一点。**

### Anti-Pattern 5: eval 不缓存生成结果，每次改指标都重跑

**What people do:** `eval.py` 一次跑生成 + 指标，改个 metric 公式就再跑 1h。
**Why it's wrong:** GGUF q4_K_M 评测 600 样本 + reasoning ≥ 30min；指标迭代被卡死。
**Do this instead:** 生成与指标分层；`gen_cache/{variant}/{sample_hash}.json` 是中间 source of truth；指标重算秒级。

### Anti-Pattern 6: 把 fp16 与 q4_K_M 评测放进训练循环

**What people do:** Trainer 的 evaluation step 内对 GGUF 量化版评测。
**Why it's wrong:** GGUF 推理路径完全不同（llama.cpp 子进程），强行接入会让训练循环不稳定 + 显著拉慢。
**Do this instead:** 训练期 eval 只看 HF fp16 学生 loss & 约束通过率；导出后单独跑全 variant matrix。

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI GPT-5.5 (teacher) | `openai` python SDK；`reasoning_effort=high`；JSON Schema 结构化输出 | 复用 `EvoProgTSC/evoprog/llm/client.py`；速率退避 + 5x 重试；429/500 都退避 |
| llama.cpp `convert_hf_to_gguf.py` | 子进程调用，传入 merged_fp16 目录 | EvoProgTSC 已 build cuda 版；脚本路径走 config |
| llama.cpp `llama-quantize` | 子进程，传入 fp16.gguf + 量化类型 | 单进程，几分钟级 |
| llama.cpp `llama-cli` / `llama-server` | eval 时调用；server 模式可批量推理 | server 模式更高吞吐；首次启动 ~30s 加载 |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| sampler ↔ teacher_label | `inputs.jsonl` 文件 | jsonl 是 stage 间通用契约 |
| teacher_label ↔ constraint_lint | `raw_responses/` 目录 | lint 永远只读 raw，可任意重跑 |
| constraint_lint ↔ dataset_builder | `labeled.jsonl` | dataset_builder 不感知教师 |
| dataset_builder ↔ trainer | `data/tokenized/` arrow + tokenizer 副本 | trainer 不重 tokenize |
| trainer ↔ exporter | `adapter/` 目录 | exporter 不感知训练 hyperparam |
| exporter ↔ evaluator | `model.{variant}.gguf` + `merged_fp16/` | evaluator 通过 variant 名路由 runner |
| 所有 stage ↔ runner | `manifest.json` | 全局可观测点；CLI 也读它做 inspect |

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **本里程碑：3000 样本，1 模型** | 当前架构刚好；单机文件系统、jsonl/arrow 全部够用 |
| 10K-30K 样本 | teacher_label 需要分批 / 断点（已支持）；dataset_builder 仍 ok（datasets 库轻松）；training 会超 6h 需要分多次或加显存策略 |
| 多模型对比（3-5 ckpt） | 当前 `runs/{ts}/` 已支持每次实验独立目录；建议加 `tsc-cycle compare run1 run2 run3` 子命令 |
| 多教师对比 | 把 `teacher.model` 写进 `cache_key`；天然多教师并存，缓存不冲突 |

### First Bottlenecks

1. **教师 API rate（最先卡）**：3000 样本 × ~3000 token output × 10 worker，按 reasoning effort high 估约 4-6h。改进顺序：先确认 RPM/TPM 限额，再上 worker 数；不要无脑提 worker。
2. **训练显存**：QLoRA r=64 + Qwen3-4B + bf16 + seq 2048 + reasoning 长度 ≈ 紧。先冒烟、再调 batch / grad_accum / 梯度 checkpointing。
3. **Eval GGUF q4_K_M 推理速度**：llama.cpp 在 GB10 上单 prompt 长 reasoning ~3-5s，600 样本 ≈ 30min；可接受但缓存必备。

---

## Sources

- Project memory: Qwen3 tokenizer 词表冲突教训（CLAUDE.md / MEMORY.md）
- Existing code: `/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py`（教师 client 复用基础）
- Reality protocol reference: `/home/samuel/TSC_CYCLE/reality.log` 行 16-82（prompt 模板与输出协议）
- DGX Spark 训练栈约束: `/dgx-spark-training` skill；GB10 aarch64 + CUDA 13 + SDPA-only
- HuggingFace Transformers Trainer `--resume_from_checkpoint` 语义（HIGH，官方文档反复验证）
- llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` 工作链（已在 EvoProgTSC 构建并验证）
- 训练环境与 OOM 防护: `/home/samuel/dgx-spark-setup` 本机仓库 + `/dgx-spark-training` skill（上游 https://github.com/natolambert/dgx-spark-setup）
- ~~waybarrios/dgx-spark-finetune-llm~~ **NOT USED**（用户明确排除；NVFP4/TRT-LLM 路径与 GGUF 目标不符）

---
*Architecture research for: LLM 蒸馏离线批处理流水线（TSC-CYCLE）*
*Researched: 2026-05-07*
