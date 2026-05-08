# Feature Research — v3.0 9B 基座切换（Qwen3.5-9B vs v1.0 Qwen3-4B-Thinking-2507）

**Domain:** TSC-CYCLE 学生模型基座升级（GPT-5.5 high → 学生 SFT 蒸馏）
**Researched:** 2026-05-08
**Confidence:** MEDIUM（架构/thinking 模式 HIGH；tokenizer 精确 token id 与自定义标签拆分行为 MEDIUM-LOW，必须由 Phase-1 dry-run 在本机实测 verified）

---

## 范围声明

本文档**只覆盖 v3.0 因 Qwen3-4B-Thinking-2507 → Qwen3.5-9B 切换而新增/变更的特性**。
**v1.0 已验证特性（数据生成器、教师 pipeline、硬约束 lint、80/10/10 split、评测套件、GGUF 导出流程）原样保留**，详见 `.planning/milestones/v2.0-abandoned/research/FEATURES.md`，本文不重复。

---

## Downstream Consumer Quick Index（roadmap & phase-1 必看）

| 关注点 | 结论 | 详细见 |
|---|---|---|
| **(a) Tokenizer 兼容性** | **MEDIUM-LOW**：Qwen3.5 切到了 **Qwen2Tokenizer (BPE)**，与 v1.0 的 Qwen3 tokenizer 同源；自定义标签 `<start_working_out>` 等 **预期仍被拆为多 sub-token**（不在 added_tokens 列表内），但**必须在 Phase-1 dry-run 用 `AutoTokenizer` 实测验证**才能据此训练 | F-T1 / F-T2 / F-T3 |
| **(b) Thinking 变体可用性** | **不存在独立的 "Thinking-only" 9B 变体**。Qwen3.5-9B 是统一模型，Small 系列（含 9B）**默认 thinking off**，需通过 chat-template 参数 `enable_thinking=true` 或 vLLM `--reasoning-parser qwen3` 打开。**官方 thinking token 仍是 `<think>`/`</think>` 单 token**（与 v1.0 相同陷阱），必须继续避开 | F-TH1 / F-TH2 / F-TH3 |
| **(c) Prompt builder 是否需改** | **不需要改 prompt 文本**（自定义标签协议沿用），但**建议在 builder 里强制不调用官方 chat_template 的 thinking branch**，并在 system prompt 显式指令模型用 `<start_working_out>` 不用 `<think>` | F-P1 / F-P2 |
| **(d) Phase-1 dry-run 验证项（风险点）** | 4 项 hard gate：① 自定义标签拆 sub-token 实测；② tokenizer vocab size & added_tokens_decoder 完整 dump；③ `convert_hf_to_gguf.py` 是否注册 Qwen3.5 架构 + GatedDeltaNet 算子；④ multimodal 权重在 text-only 加载时是否能干净跳过 vision encoder | F-V1 ~ F-V4 |

---

## Feature Landscape

### Table Stakes（v3.0 必须新增/调整的特性，缺一项端到端流水线无法跑通）

| ID | Feature | 用户期望（v3.0 视角） | 与 v1.0 差异 | 复杂度 | Notes |
|---|---|---|---|---|---|
| **F-T1** | **Qwen3.5-9B tokenizer 安全断言** | 启动时 assert：`<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 都被 BPE 拆成 ≥2 sub-tokens；且不命中 added_tokens（`<think>`/`</think>` 在 Qwen3.5 是单 token，仍要避开） | v1.0 也做这个断言，但**比对的 token id 不一样**（Qwen3 是 151667/151668；Qwen3.5 待 dry-run 实测，不要复用旧常量） | LOW | 复用 v1.0 `tokenizer_safety.py`，把 hard-coded id 抽成"运行时从 tokenizer 查询"的动态值 |
| **F-T2** | **Qwen3.5 tokenizer 实测 dump（Phase-1 hard gate）** | Phase-1 必须运行：`AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")` → 写 `runs/dryrun/tokenizer_audit.json`，含完整 `added_tokens_decoder`、`<think>`/`</think>` token id、4 个自定义标签的 token id 列表 | v1.0 没有这个独立审计文件 | LOW | dry-run 输出供 roadmap 后续 phase 引用，避免训练时再 surprise |
| **F-T3** | **自定义标签拆分行为不退化保证** | 自定义标签必须保持**多 sub-token**（与 v1.0 行为对齐）；如果 Qwen3.5 因新增 vision/audio 词汇导致 BPE merges 改变、把某个自定义标签 collapse 成单 token，则该标签必须被替换 | v1.0 没遇到这个风险（同 tokenizer 系列） | LOW（如出问题 MEDIUM） | 备选标签池：`<reasoning_open>` / `<reasoning_close>` / `<answer_open>` / `<answer_close>`；只在 F-T2 dry-run 失败时启用 |
| **F-TH1** | **Thinking 模式默认关闭（与 v1.0 相反）** | Qwen3.5 Small 系列（0.8B/2B/4B/9B）**默认 thinking 关闭**；Qwen3-4B-Thinking-2507 是默认开启 | **重大差异**：v1.0 学生本来就在 thinking 模式蒸馏；v3.0 模型在"非 thinking"基线上启动 SFT，需要 SFT 把"输出自定义思考标签"作为新行为完整教会 | MEDIUM | 不是问题：本项目本来就强迫学生输出**自定义**标签而非 `<think>`，与"是否默认 thinking"解耦；但需要确认 system prompt + assistant target text 在该模式下不会被 chat_template 静默剥离 |
| **F-TH2** | **不依赖 Qwen3.5 原生 `<think>` token** | 与 v1.0 同：训练 target 中**禁止出现** `<think>`/`</think>`（Qwen3.5 中 id 待实测，但仍是单 added token，与 v1.0 同陷阱） | 同 v1.0 | LOW | 复用 v1.0 训练前数据 lint：扫描所有 SFT target 字符串，确保不含 `<think>` `</think>` 文本（防教师"反吐"） |
| **F-TH3** | **`enable_thinking` chat-template 参数显式 false** | 凡是构造 prompt（训练拼接、推理评测）都显式传 `tokenizer.apply_chat_template(..., enable_thinking=False)`，避免自动注入 `<think>` 占位 | v1.0 模型默认就 thinking on，没这个参数差异 | LOW | 单点改 `prompt_builder.py`；qwen3 的 `/think`/`/nothink` soft switch 在 Qwen3.5 已**官方移除** |
| **F-P1** | **prompt builder 不变文本协议** | system + user 文本与 reality.log 协议保持完全一致；assistant target 包裹仍为 `<start_working_out>...<end_working_out><SOLUTION>{json}</SOLUTION>` | 文本零改动 | LOW | 验证 v2.0 Phase 7 已落地的标签修正（`<end_working_out>` 而非 `</end_working_out>`）继续有效 |
| **F-P2** | **chat_template 隔离层** | 不直接调用 Qwen3.5 自带 `chat_template`（含 thinking 分支、tool-call 分支、vision 占位），而是用项目自定义 minimal template：`{system}\n{user}\n{assistant_target}` | v1.0 也是自定义 template，但要重新审计 Qwen3.5 是否引入新的 special-token 副作用（如 `<|vision_start|>` 在纯文本输入中不应出现） | LOW | 在 prompt builder 加正则 guard：output 串中不允许出现任何 `<|...|>` special token |
| **F-M1** | **9B 加载 + QLoRA r=64 + batch_size=1 显存核算** | 单卡 4-bit NF4 加载 9B（~5.5–6 GB 权重）+ LoRA r=64 adapters + activations + 优化器状态；DGX Spark 100GB unified memory 下 max_seq=2048 + batch=1 + grad_accum=32 应留 ≥30GB 余量 | v1.0 是 4B（~2.4 GB 权重），余量大很多 | MEDIUM | Phase-1 dry-run 必须实测 peak memory；若 OOM：先降 max_seq → 1536，再 `bnb_4bit_use_double_quant=False`（牺牲一点精度换显存） |
| **F-M2** | **Multimodal 权重的 text-only 加载** | Qwen3.5-9B 是 native multimodal（early-fusion，不是 bolt-on）；HF Transformers 加载默认会拉 vision encoder 权重；本项目纯文本，需要要么 `--language-model-only`（vLLM 的概念，HF Transformers 没直接对应 flag），要么验证文本通路不触发 vision projector | v1.0 4B-Thinking 是纯文本模型，无此问题 | MEDIUM | Phase-1 dry-run 需确认：(a) `Qwen3_5ForCausalLM` vs `Qwen3_5ForConditionalGeneration` 哪个 class、(b) 加载时 vision tower 是否能 lazy / 跳过、(c) GGUF 导出是否需要单独 mmproj 文件（参考 unsloth/Qwen3.5-9B-GGUF 与 jc-builds VLM-Q4_K_M 的输出对比） |
| **F-G1** | **llama.cpp `convert_hf_to_gguf.py` 注册 Qwen3.5 架构** | 本机 llama.cpp build（EvoProgTSC 仓库）需 `git pull` 升级到含 Qwen3.5 architecture-mapping 的版本；社区证实 Qwen3.5-9B-Instruct 的 tokenizer hash 已 land 到 master | v1.0 用的是已注册的 `Qwen3ForCausalLM`（脚本第 4551 行）；Qwen3.5 是新 entry | MEDIUM | Phase-1 hard gate：跑 `python convert_hf_to_gguf.py --help` 后 `grep -i qwen3.5` 验证；若未注册，则升级 llama.cpp 到 master + 重新 `make`（CUDA 13 aarch64 build） |
| **F-G2** | **GatedDeltaNet 混合注意力的 GGUF 算子兼容** | Qwen3.5 用 hybrid Gated DeltaNet + Gated Attention（与 Qwen3-Next 同思路）；llama.cpp 在 PR #19408（2026-02 merge）后已支持 Qwen3-Next 80B 的 hybrid 推理，9B 路径**应**沿用 | **新风险**：这是 v1.0 完全没有的算子；如果 Qwen3.5-9B 走和 Qwen3-Next 不同的 hybrid stack，GGUF 推理可能有崩塌点 | HIGH | Phase-1 hard gate：导出 fp16 GGUF 后，用 `llama-cli` 跑一条 reality.log prompt，肉眼对比 HF bf16 输出格式与数值一致性（≥80% phase 数字相同视为通过） |
| **F-G3** | **q4_K_M 量化稳定性（思考链长输出对量化更敏感）** | Qwen3.5 Reasoning 模式输出极度 verbose（官方报告 200M tokens vs 23M 平均，约 9× 长度）；Q4_K_M 在长思考链上更易崩塌（重复、格式破裂） | v1.0 4B 思考链短，q4_K_M 衰减仅 0.6pp；9B 风险显著上升 | HIGH | 两个对策叠加：(a) 量化时启用 `--imatrix`，用 SFT 训练子集 50-100 条做重要性矩阵；(b) 评测套件对 q4_K_M 加"长思考链稳定性"指标（输出长度方差 + 思考标签完整率），若 ratio < 0.95 则降级到 q5_K_M 或 q8_0 |

### Differentiators（能让 9B 切换比 v1.0 4B 拿到更多收益的可选增量）

| ID | Feature | 价值 | 复杂度 | 优先级 |
|---|---|---|---|---|
| **F-D1** | **9B reasoning 容量利用：训练样本 max_seq 提升到 4096** | 9B 能 hold 住更长思考链，让教师 verbose reasoning 不被截断 | LOW（仅改 config） | High（v1.0 是 2048，截断率约 3%；9B 教师在 reasoning_effort=high 下可能更长） |
| **F-D2** | **Imatrix 校准量化** | 用 SFT 训练子集生成 importance matrix，q4_K_M 输出质量显著提升 | LOW | High（F-G3 风险对冲） |
| **F-D3** | **量化分级对比（fp16 / q5_K_M / q4_K_M / q4_K_S）** | 9B 体积更大（fp16 ≈ 18GB → q4_K_M ≈ 5.5GB），分级对比给部署端选择 | LOW | Medium |
| **F-D4** | **基线对比报表：v1.0 vs v3.0 端到端 delta** | 必备，证明 9B 升级带来实际收益（或反证 4B 已是甜点） | LOW | High |
| **F-D5** | **Thinking-mode 双跑评测（enable_thinking on vs off）** | 9B 在两种模式下都能跑；评测数据可能揭示"我们的 SFT 是否实际上用了 thinking pathway" | MEDIUM | Medium |
| **F-D6** | **教师 reasoning_effort 上限不变（仍 high）但样本数选项 3000 / 6000 对照** | 9B 模型容量更大，可能受益于更多样本；做小规模 1000-sample 对照判断是否值得扩量 | LOW（首轮仍 3000） | Low |

### Anti-Features（v3.0 明确不做）

| Anti-Feature | 不做的原因 | 替代做法 |
|---|---|---|
| **直接复用 Qwen3.5 原生 `<think>`/`</think>` token** | 与 v1.0 同陷阱：单 added token，预训练有先入语义；Qwen3.5 中虽然 token id 不同（实测确认）但仍是单 token | 沿用自定义多 sub-token 标签 |
| **启用 vision/audio 多模态训练** | 项目纯文本 TSC 决策；引入 vision encoder 权重 + 训练只是浪费显存 | text-only 加载；不传 image_pad/vision_start 任何 special token |
| **加 special_tokens 把 `<start_working_out>` 等加进 vocab** | v1.0 已论证：会触发 `resize_token_embeddings`，新 embedding 训不充分，q4_K_M 量化后乱码 | 保持文本标签自然 BPE 拆分 |
| **batch_size > 1** | 用户明确要求 batch=1（与 9B 显存压力一致） | gradient_accumulation_steps 调高（如 32 或 64）保持 effective batch ≈ 32 |
| **vLLM 推理（即便 Qwen3.5 官方推荐 vLLM）** | 本机 vLLM 不可用；最终部署是 llama.cpp/GGUF | HF Transformers `generate()` 评测 + llama.cpp 部署 |
| **YaRN 扩展到 1M context** | TSC prompt 实测 < 4K tokens，extended context 用不到，且 thinking 模式下 Qwen 官方建议 ≥128K（这是为长思考预留的，不是为输入） | max_seq 锁 4096 或更小 |
| **Soft-switch `/think` `/nothink`** | Qwen3.5 **官方已移除**该机制 | 用 `enable_thinking` chat-template 参数；本项目用自定义标签，不依赖任一原生 thinking 机制 |
| **采用 Qwen3.5-9B-Base（无 Instruct/Reasoning post-training）** | Base 模型缺 SFT 基础对齐，从 base 起步要更多数据；本项目 3000 样本预算，需用已 instruct/reason 后训的版本 | 用 Qwen3.5-9B（默认 reasoning post-trained 版） |
| **Unsloth save_pretrained_gguf 链路** | 与 v1.0 同决策：使用本机 llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` 直接两步 | 沿用 v1.0 GGUF 导出脚本，仅替换 architecture 注册检查 |
| **改训练框架（Unsloth on Spark / Axolotl）** | PROJECT.md 显式 Out of Scope；锁 v1.0 已验证 TRL+PEFT+bnb 栈 | 复用 `/dgx-spark-setup/.venv` |

---

## Feature Dependencies

```
[F-T2 tokenizer dump (Phase-1 dry-run)]
        ├──> [F-T1 安全断言运行时常量化]
        ├──> [F-T3 自定义标签退化检查]
        └──> [F-TH2 训练数据 lint 不含 <think>]
                                            ↓
[F-M1 9B + bnb 4bit + r=64 显存实测] ──┐    │
[F-M2 multimodal text-only 加载验证] ──┼──> [QLoRA SFT 训练循环]
                                        │    ↓
                              [F-P1/F-P2 prompt builder]
                                             ↓
                              [LoRA merge → fp16 HF]
                                             ↓
[F-G1 llama.cpp Qwen3.5 注册检查] ──────────> [convert_hf_to_gguf]
[F-G2 GatedDeltaNet GGUF 算子] ─────────────> 同上 + smoke test
                                             ↓
[F-G3 q4_K_M 长思考链稳定性] ───────────────> [量化 + 评测]
[F-D2 imatrix 校准]              ───────────> 同上（对冲）
                                             ↓
                             [F-D4 v1.0 vs v3.0 delta 报表]
```

**关键依赖链：**
- **F-T2 是上游 hard gate**：tokenizer dump 不出 → 后续所有 token 相关工作全部 block。
- **F-G1 与 F-G2 必须 Phase-1 先验证**，否则训练完成后才发现 GGUF 导不出，6h 训练 sunk cost。
- **F-M2 multimodal 加载** 决定是否要 patch HF Transformers 加载逻辑；如不能 cleanly 加载文本部分，需提前评估迁移到 Qwen3.5-9B-Base（虽然 base 在 Anti-Features，但是是 P1 fallback）。

---

## MVP Definition

### Launch With (v3.0)

按 Feature Dependencies 上游优先：

- [ ] **F-T2** Phase-1 tokenizer audit：dump added_tokens_decoder + 自定义标签 token 列表 + `<think>`/`</think>` id（**hard gate**）
- [ ] **F-G1 + F-G2** Phase-1 GGUF dry-run：本机 llama.cpp 是否注册 Qwen3.5 架构；导出 fp16 GGUF 并 smoke 推理（**hard gate**，决定环境是否需升级 llama.cpp）
- [ ] **F-M1 + F-M2** Phase-1 加载 dry-run：4bit 加载 9B、文本前向 forward 一条 prompt、记录 peak memory；确认 vision encoder 不污染（**hard gate**）
- [ ] **F-T1** tokenizer 安全断言重构：把 v1.0 hard-coded `<think>` id 抽成运行时查询
- [ ] **F-T3** 自定义标签退化检查：4 个标签都 ≥2 sub-tokens；如有退化启用备选标签池
- [ ] **F-TH1 + F-TH2 + F-TH3** prompt 构造侧 thinking 适配：`enable_thinking=False`、target 文本不含原生 `<think>`
- [ ] **F-P1 + F-P2** prompt builder 隔离层：自定义 minimal template，guard special tokens
- [ ] **F-G3 + F-D2** q4_K_M 稳定性保险：同时跑 imatrix 校准 + 评测加"思考链长度方差 + 标签完整率"
- [ ] **F-D4** v1.0 vs v3.0 端到端 delta 报表

### Add After Validation (v3.x)

- [ ] **F-D1** max_seq 提升到 4096（视 9B 显存余量）
- [ ] **F-D3** 量化分级对比（q5_K_M / q4_K_S）
- [ ] **F-D5** thinking on/off 双跑评测

### Future Consideration (v4+)

- [ ] **F-D6** 样本扩量到 6000（仅在 v3.0 ratio<0.95 或泛化 gap>5pp 时考虑）

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| F-T2 tokenizer audit dry-run | HIGH | LOW | **P1（hard gate）** |
| F-G1 llama.cpp 注册检查 | HIGH | LOW | **P1（hard gate）** |
| F-G2 GatedDeltaNet GGUF 算子 smoke test | HIGH | MEDIUM | **P1（hard gate）** |
| F-M1 9B 显存实测 | HIGH | LOW | **P1（hard gate）** |
| F-M2 multimodal text-only 加载 | HIGH | MEDIUM | **P1（hard gate）** |
| F-T1 / F-T3 tokenizer 安全 | HIGH | LOW | P1 |
| F-TH1/2/3 thinking 适配 | HIGH | LOW | P1 |
| F-P1 / F-P2 prompt builder | HIGH | LOW | P1 |
| F-G3 q4_K_M 稳定性保险 | HIGH | MEDIUM | P1 |
| F-D2 imatrix 校准 | MEDIUM | LOW | P1（对冲 F-G3） |
| F-D4 v1.0 vs v3.0 delta 报表 | HIGH | LOW | P1 |
| F-D1 max_seq 4096 | MEDIUM | LOW | P2 |
| F-D3 量化分级对比 | MEDIUM | LOW | P2 |
| F-D5 thinking on/off 双跑 | MEDIUM | MEDIUM | P2 |
| F-D6 样本扩量到 6000 | MEDIUM | HIGH（教师 API 成本） | P3 |

---

## Phase-1 Dry-Run Hard Gates 总结（给 roadmap 起 phase）

任一 fail 必须在进入 Phase-2 训练前解决：

1. **Tokenizer gate (F-T2/T3)**：`AutoTokenizer` 加载成功；4 个自定义标签都拆 ≥2 tokens；`<think>` 单 token id 已记录但**不出现在训练数据**。
2. **加载 gate (F-M1/M2)**：4bit 加载 + 一次 forward 通过；peak memory 记录；vision encoder 权重要么不加载、要么加载但不参与 forward。
3. **导出 gate (F-G1/G2)**：本机 llama.cpp 能识别 Qwen3.5 架构；fp16 GGUF 导出后 `llama-cli` smoke 推理输出格式与 HF bf16 一致。
4. **Prompt gate (F-P1/P2/TH3)**：`apply_chat_template(enable_thinking=False)` 输出文本不含 `<|vision_*|>` 或 `<think>`；自定义 minimal template 与 reality.log 协议一致。

任一 hard gate fail 时的 fallback 决策树：

| Gate | Fallback 1 | Fallback 2 | Abandon trigger |
|---|---|---|---|
| Tokenizer | 启用备选标签池（F-T3 备份） | 切到 Qwen3.5-9B-Base | 备选池标签也 collapse |
| 加载 | 升 max_seq 截断 / 关 double_quant | 切 r=32 LoRA | 9B + 100GB 仍 OOM |
| 导出 | `git pull` llama.cpp + 重 build | 等待社区 PR / 临时用 HF bf16 部署 | GatedDeltaNet 算子缺失且无可用分支 |
| Prompt | 手写 template（不调用 apply_chat_template） | — | — |

---

## v1.0 → v3.0 Feature Diff 一页表（roadmap 直接引用）

| 维度 | v1.0 (Qwen3-4B-Thinking-2507) | v3.0 (Qwen3.5-9B) | 影响 |
|---|---|---|---|
| 模型大小 | 4B dense | 9B dense + vision encoder | 显存 +3.5×；F-M1/M2 |
| 架构 | 标准 attention | Hybrid Gated DeltaNet + Gated Attention | F-G2 GGUF 算子风险 |
| Thinking 默认 | ON（Thinking 专用模型） | OFF（Small 系列默认非 thinking） | F-TH1/3 |
| `<think>` token id | 151667 / 151668 | 待 dry-run 实测（不要假设） | F-T1/T2 |
| Tokenizer 类 | Qwen3 (BPE 系列) | Qwen2Tokenizer (BPE) | 同源；F-T2 实测确认 |
| Vocab 范围 | ~152K | 待实测（文献提及但来源 LOW） | F-T2 实测，禁止假设具体数字 |
| 自定义标签 collapse 风险 | 已验证：4 个全部 ≥2 sub-tokens | 预期延续；MEDIUM 风险 | F-T3 |
| Native 多模态 | 否 | 是（early-fusion，含 vision encoder） | F-M2 + F-G1 mmproj 处理 |
| Soft switch /think | N/A | 官方移除 | F-TH3 用 chat-template 参数 |
| Reasoning 输出长度 | 中等 | ~9× 平均（官方 200M vs 23M 评测 token 数） | F-D1 max_seq 4096；F-G3 q4 稳定性风险 |
| llama.cpp 支持 | `Qwen3ForCausalLM` 已注册 | `Qwen3.5` tokenizer hash 已 land；架构需核实 | F-G1 hard gate |
| Context window | 262K | 262K（thinking 推荐 ≥128K，但本项目 max_seq ≤4K 不触发） | 无影响 |
| QLoRA 显存（NF4 + r=64） | ~30-40 GB peak (4B) | 待实测（预估 60-75 GB） | F-M1 hard gate |

---

## Risk Register（高优先级风险点，要求 Phase-1 dry-run 验证）

| 风险 | 严重度 | 触发概率 | 缓解 | 验证方式 |
|---|---|---|---|---|
| 自定义标签因 Qwen3.5 新词表（vision/audio token）BPE merges 改变而被 collapse | HIGH | LOW-MEDIUM | F-T3 备选标签池 | F-T2 dry-run 实测 |
| llama.cpp 未注册 Qwen3.5 架构 / GatedDeltaNet 算子缺失 | HIGH | MEDIUM | `git pull` + 重 build；最坏情况临时用 HF bf16 部署 | F-G1/G2 dry-run smoke test |
| 9B + r=64 + double_quant 在 100GB unified memory 上 OOM | MEDIUM | LOW（4bit 9B 余量充裕） | 关 double_quant / r=32 / max_seq=1536 | F-M1 dry-run peak memory |
| HF Transformers 加载 multimodal 检查点时强制拉 vision encoder，触发 OOM 或加载错 class | MEDIUM | MEDIUM | 用 `Qwen3_5ForCausalLM`（如存在）或 patch；最坏切 9B-Base | F-M2 dry-run |
| q4_K_M 在 9B 长思考链上输出崩塌（重复 / 格式破裂），ratio < 0.95 | MEDIUM | MEDIUM-HIGH | imatrix 校准 + 量化分级 fallback (q5_K_M) | F-G3 评测阶段 |
| Qwen3.5-9B 的"reasoning post-trained"先验与本项目自定义标签冲突（学生倾向输出 `<think>`） | MEDIUM | MEDIUM | 训练数据 lint + system prompt 强约束；2 epochs 起步 | 训练后 generation 抽查 |
| `enable_thinking=False` 下 chat_template 静默剥离思考段，破坏 SFT label | LOW | LOW | F-P2 自定义 minimal template 完全绕开官方 chat_template | F-P1/P2 验证 |

---

## Sources & Confidence

| Source | Confidence | 用于支持 |
|---|---|---|
| [Qwen/Qwen3.5-9B HF model card](https://huggingface.co/Qwen/Qwen3.5-9B) | HIGH | 9B 存在；多模态 early-fusion；262K context；Qwen2Tokenizer |
| [Unsloth Qwen3.5 docs](https://unsloth.ai/docs/models/qwen3.5) | HIGH | Small 系列默认 thinking off；`enable_thinking=true` chat-template 参数；soft-switch 已移除 |
| [vLLM Qwen3.5/3.6 recipes](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) | HIGH | `--language-model-only` flag；`--reasoning-parser qwen3` |
| [Artificial Analysis: Qwen3.5 small models](https://artificialanalysis.ai/articles/qwen3-5-small-models) | MEDIUM | thinking 模式输出极度 verbose（200M vs 23M tokens） |
| [llama.cpp Issue #15940 — Qwen3-Next support](https://github.com/ggml-org/llama.cpp/issues/15940) | HIGH | GatedDeltaNet hybrid arch 在 llama.cpp 的支持节点 |
| [llama.cpp PR #19408](https://github.com/ggml-org/llama.cpp/pull/19408) | HIGH | hybrid arch 已 working（Qwen3-Next 80B 跑通） |
| [unsloth/Qwen3.5-9B-GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) | MEDIUM | 9B GGUF 量化版本社区已可得，间接证实 convert_hf_to_gguf 路径可行 |
| [Oflight Qwen3.5-9B fine-tuning guide](https://www.oflight.co.jp/en/columns/qwen35-9b-fine-tuning-guide) | LOW-MEDIUM | QLoRA 16GB 可跑；nf4 + double_quant + bf16 配方 |
| [WebFetch tokenizer_config.json dump](https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/tokenizer_config.json) | **LOW**（疑似 hallucination：报告 vocab 248K，与 Qwen 系列已知 ~152K 矛盾；Phase-1 必须实测推翻或确认） | added_tokens 列表与 `<think>` id；当前**不应**作为权威值使用 |
| [v1.0 FEATURES.md](file:///home/samuel/TSC_CYCLE/.planning/milestones/v2.0-abandoned/research/FEATURES.md) | HIGH | v1.0 已验证 baseline，v3.0 不重复研究 |
| [TSC-CYCLE MEMORY.md](file:///home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/MEMORY.md) | HIGH（**注**：86 天前的快照，但 token id/added-token 性质属于模型版本固定属性，仍可信） | Qwen3 tokenizer added-token 陷阱；2 epochs 经验 |

**Overall confidence: MEDIUM。** 架构、thinking 模式、llama.cpp 路径都有 HIGH 来源；唯一 LOW 区是 Qwen3.5-9B 精确 token id 与自定义标签的拆分行为——这两者都是 Phase-1 dry-run 5 分钟可决定的实测项，**不应**作为研究阶段的阻塞。Roadmap 应将其编入 Phase 1（dry-run / feasibility validation）作为 hard gate。
