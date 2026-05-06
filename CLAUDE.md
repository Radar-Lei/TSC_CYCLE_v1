<!-- GSD:project-start source:PROJECT.md -->
## Project

**TSC-CYCLE — 思考型 4B 学生模型蒸馏**

把 GPT-5.5 high（教师）在「交通信号配时（TSC）周期绿灯时长决策」任务上的能力，
通过合成数据 SFT 蒸馏到 Qwen3-4B-Thinking-2507（学生），最终产出能在本地以
GGUF（fp16 + q4_K_M）部署、且带显式思考过程的 4B 推理模型。

服务对象是 EvoProgTSC 系列项目中需要「便宜、可本地部署、可解释」的 TSC 决策端点。

**Core Value:** 学生模型在 OOD（reality.log 分布之外的合成输入）上仍然满足全部硬约束
（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），
并在数值决策上接近 GPT-5.5 high 教师 —— 不是过拟合到 reality.log。

### Constraints

- **Tech stack**: 学生 = Qwen3-4B-Thinking-2507；训练 = QLoRA r=64（HF Transformers + PEFT 或 Unsloth，待 RESEARCH 验证）；蒸馏 API = OpenAI gpt-5.5 + reasoning_effort=high；导出 = llama.cpp GGUF
- **Hardware**: DGX Spark GB10 aarch64 CUDA 13；遵循 `/dgx-spark-training` 全部约束（无 flash-attn cu12、SDPA、swap/OOM 防护、复用已知良好 venv）
- **Timeline**: 单次端到端微调（不含数据生成）控制在 **6 小时以内**；数据生成单独的 4–6h 阶段
- **API**: 教师 API 并发 ≤ **10 worker**；遇 RPM/TPM 触发指数退避
- **Budget**: GPT-5.5 high 调用以 3000 样本为预算上限的设计点；超出需另议
- **Tokenizer 安全**: 训练任何思考标签都必须验证它会被拆成多个 sub-token（不在词表内、且不与原生 `<think>` 冲突）
- **数据约束**: 教师输出必须通过硬约束 lint（min/max/整数/相位覆盖）才能进训练集
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Executive Recommendation（一句话）
## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | 3.12 | Runtime | dgx-spark-setup 已锁 3.12；cu130 aarch64 wheel 也对应 cp312 |
| **PyTorch** | `>=2.9.0+cu130` | 深度学习框架 | dgx-spark-setup 验证可用；aarch64 cu130 wheel 存在；忽略 sm_120/sm_121 binary-compatible 警告即可 |
| **Transformers** | `>=4.56.2`（官方 Unsloth-on-Spark 锁定）；本项目建议 `>=4.56.2,<5.0` | HF 模型加载、SFT trainer 上游 | Qwen3-4B-Thinking-2507 需要 `transformers>=4.51`；4.56.2 是 Unsloth Spark Dockerfile 的稳定锚点 |
| **TRL** | `0.22.2`（与 Spark Dockerfile 对齐）或 `>=0.22.0,<0.27` | `SFTTrainer` 蒸馏训练 | TRL 0.22.x 与 transformers 4.56.x、PEFT 0.15.x 相互兼容；NVIDIA Spark playbook 验证 |
| **PEFT** | `>=0.15.1` | LoRA / QLoRA adapter | dgx-spark-setup 验证；r=64 配置成熟 |
| **bitsandbytes** | `0.48.0` | 4-bit NF4 量化加载基座 | Unsloth Spark Dockerfile 锁 0.48.0；aarch64 wheel 存在；sm_121 通过 PTX JIT（无 native cubin 但 sm_100→sm_121 可 JIT） |
| **Accelerate** | `>=1.6.0` | 分布式/混合精度封装 | dgx-spark-setup 锁定；单卡 bf16 路径稳 |
| **Datasets** | `>=3.1.0`（Spark playbook 用 4.3.0 也可） | SFT 数据 IO | 标准 HF 栈 |
| **Triton** | 与 PyTorch 2.9.0+cu130 捆绑 | 内核 JIT | 必须 `export TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas` 否则 `sm_121a` 报错 |
| **OpenAI Python SDK** | `>=1.50.0`（支持 `responses.create` + `reasoning={"effort": "high"}`） | 教师 API 客户端 | gpt-5.5 走 Responses API；旧 `chat.completions` 也接受 `reasoning_effort` 字符串参数（`EvoProgTSC/client.py` 用法仍可工作） |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **llama.cpp** | 本机已 build：`/home/samuel/projects/EvoProgTSC/llama.cpp`（含 `convert_hf_to_gguf.py` + `llama-quantize` 二进制） | Merge 后 HF→GGUF→Q4_K_M | 第 7 步导出阶段；`Qwen3ForCausalLM` 已注册（convert 脚本第 4551 行）；`llama-quantize` Q4_K_M=preset 15 |
| **safetensors** | `>=0.4.0`（transformers 依赖自动满足） | 权重序列化 | merge LoRA 后保存 fp16 |
| **wandb** | `>=0.18.1` | 训练观测 | 6h 训练强烈建议开 tracking |
| **rich** | `>=14.0.0` | 控制台日志 | dgx-spark-setup 默认包含 |
| **tenacity** 或自写指数退避 | `>=8.2.0`（如选 tenacity） | API 重试 | 教师标注阶段；`EvoProgTSC/client.py` 自写循环也直接复用 |
| **jsonschema** | `>=4.20.0` | 教师输出硬约束 lint | 校验 `final_green` 整数、`min_green ≤ x ≤ max_green`、相位覆盖 |
| **pydantic** | `>=2.5.0` | 数据模型 / 类型化 | 训练样本、教师响应的 schema |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | 包管理 | `uv venv` / `uv pip install`；dgx-spark-setup 全栈用 uv，不要混用 pip |
| **systemd-run --scope** | OOM 防护 | 训练必须包在 `MemoryMax=100G MemorySwapMax=0` 内（unified memory 死锁防护） |
| **swap off** | OOM 防护前置 | `sudo swapoff -a`；DGX Spark 必做，否则 OOM 整机僵死 |
| **TensorBoard 或 wandb** | 训练曲线 | wandb 优先（远程可看） |
## Installation
# 进入已知良好 venv
# 追加 SFT 蒸馏专用依赖（不要重装 torch / vllm）
# 验证（必须全部 OK）
# llama.cpp（已 build，无需重装）
## Key Configuration Decisions
### QLoRA r=64 配置（Qwen3-4B-Thinking-2507）
### Model Loading（强制 SDPA）
### SFT Trainer（TRL）
### 自定义思考标签 tokenizer 处理
## OpenAI 教师 API 模式（基于 `EvoProgTSC/client.py` 复用）
### 现有 `StrategyLLMClient` — 直接可复用部分
| 复用项 | 来源 | 说明 |
|--------|------|------|
| `BadRequestError` 自动降级（结构化输出失败时切普通调用） | `client.py:113-123, 157-164` | 结构化输出 → JSON Schema strict 模式，不行就降级 |
| `APITimeoutError` / `APIConnectionError` / `APIError` 指数退避 | `client.py:166-191` | `delay = base * 2^attempt`，最多 `max_retries` 次 |
| `reasoning_effort` 字符串透传 | `client.py:152-153` | 设置 `reasoning_effort="high"` 即可 |
| 失败返回 `LLMResult(success=False)` 而非抛异常 | 通篇 | 并发场景容错友好 |
### 必须新增的部分（写在新模块 `tsc_cycle/teacher/labeler.py`）
| 新增项 | 实现要点 |
|--------|---------|
| **并发池（≤10 worker）** | `concurrent.futures.ThreadPoolExecutor(max_workers=10)` + `as_completed` 收集 |
| **JSON Schema 适配 TSC 输出** | 替换 `STRATEGY_SCHEMA`：properties 改为 `{"phase_greens": {"type": "array", "items": {"type": "integer"}}, "reasoning_summary": {"type": "string"}}`；strict=True |
| **思考标签包装** | 教师 system prompt 显式约束输出格式 `<start_working_out>...</end_working_out><SOLUTION>{json}</SOLUTION>`；`_parse_response` 改为先 regex 切两段，再对 SOLUTION 段 `json.loads` |
| **硬约束 lint pass** | 解析 JSON 后立即跑 `validate_constraints(input, output)`：min/max/整数/相位覆盖；不通过则丢弃，**不重试**（重试会过拟合到这一组难例）|
| **base_url 切回 OpenAI 官方** | 现有 client 默认 `localhost:1234/v1`（LM Studio）；蒸馏改 `base_url=None`（用 `openai.OpenAI()` 默认）+ `api_key=os.environ["OPENAI_API_KEY"]` |
| **Rate limit 退避** | OpenAI 的 `RateLimitError` 单独捕获，sleep 60s 后重试（`Retry-After` header 优先），不计入 `max_retries` |
| **进度持久化** | 每个样本结果写 JSONL append，重启可断点续跑（3000 样本预算下重要） |
### Pseudocode
## GGUF 导出 Pipeline（端到端验证）
### 第一步：merge LoRA → fp16 HF 权重
### 第二步：HF → GGUF fp16
### 第三步：fp16 → Q4_K_M 量化
### Tokenizer 注意事项（自定义标签）
- 自定义标签 `<start_working_out>` 等会被 Qwen3 BPE 拆成 sub-token，`convert_hf_to_gguf.py` 把 tokenizer 完整序列化到 GGUF metadata，**不需要把它们注册成 added_tokens**。
- 如果训练时把它们错误地 `add_tokens()` 加进 vocab 并 `resize_token_embeddings()`，convert 脚本仍能处理（Qwen3 走 BPE pre-tokenizer），但 q4_K_M 量化后这些新 token 的 embedding 质量会下降。**结论：保持训练时不动 vocab，只在 prompt template 里写文本标签**。
- 量化前后跑同一组测试 prompt，对比输出格式完整性（思考段+SOLUTION 段是否齐全），是检测「q4_K_M 崩塌」的最快信号。
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **TRL+PEFT+bitsandbytes**（本项目方案） | **Unsloth** | Unsloth 在 DGX Spark 上**可以**跑（Unsloth 官方有 Spark 教程，pin `bitsandbytes==0.48.0`），但需要：(a) NGC 容器或自建 Triton/xformers from source；(b) `transformers` 打 monkey-patch 才能加载 GPT-OSS 类模型；(c) `save_pretrained_gguf` 在 >50GB 模型有 bug（Issue #3861），4B 不触发但闭源调用链增加调试难度。**只有在 6h 预算放宽、且需要 8× 长 context 时才换 Unsloth** |
| **TRL+PEFT** | **Axolotl** | Axolotl 配置驱动很好，但 aarch64 cu130 兼容性未在 dgx-spark-setup 中验证；本项目 6h 单脚本闭环更简单 |
| **TRL+PEFT** | **ms-swift** | ModelScope 维护，命令行体验好，但本项目教师/学生/评测都是自写 Python，统一在 PyTorch 原生栈更易调试 |
| **本机 llama.cpp 手动两步** | `Unsloth.save_pretrained_gguf` | Unsloth 该 API 在 4B 应该工作，但**不依赖 Unsloth → GGUF 链路**（Issue #3861 是 50GB 阈值 bug，但显示其内部 wrapper `unsloth_convert_hf_to_gguf.py` 有自定义改动）；本机 llama.cpp 是 EvoProgTSC 已 build cuda 版的产物，更稳 |
| **OpenAI Responses API** | **Chat Completions API** | gpt-5.5 在两个 API 都接受 `reasoning_effort`，Chat Completions 与 `EvoProgTSC/client.py` 现有代码兼容性更好；**保持 chat.completions.create**，新版 SDK 会传 `reasoning_effort` 字段 |
| **ThreadPoolExecutor 并发** | **OpenAI Batch API** | Batch API 更便宜（约 50% off），但延迟 ~24h，且无法做硬约束 lint+丢弃+重生成的快速循环。3000 样本 @ ≤10 worker 同步调用预计 30–60 min，可控 |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **flash-attn (PyPI)** | 无 cu130 aarch64 wheel；`libcudart.so.12` 报错；即使从源码 build，sm_121 不支持，且 SDPA 在 Blackwell 上更快 | `attn_implementation="sdpa"` |
| **vLLM**（用于训练或推理） | 本机现状不可用；DGX Spark cu130 wheel 是 nightly，且本项目目标部署是 GGUF | `transformers.generate()` 跑评测；GGUF + `llama-cli` 跑最终推理 |
| **Unsloth `save_pretrained_gguf`** | Issue #3861（>50GB bug）+ 内部 `unsloth_convert_hf_to_gguf.py` 有自定义 fork，调试链长 | 本机 `convert_hf_to_gguf.py` + `llama-quantize` 两步 |
| **Qwen3 原生 `<think>` token** | MEMORY 已验证：tokenizer 中是单 token（id 151667/151668），有预训练语义包袱，自定义 SFT 会语义冲突 | `<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 文本标签（多 sub-token） |
| **`pip install vllm` / `pip install flash-attn`** | 默认走 cu12 wheel，必报 `libcudart.so.12 not found` | 整个项目不需要这两个包 |
| **`add_special_tokens=True` 把自定义思考标签加进 vocab** | 会触发 `resize_token_embeddings`，新 embedding 训不充分；q4_K_M 后这些 token 输出会乱码 | 保持文本标签，BPE 自然拆 sub-token |
| **packing=True（SFTTrainer）** | 把多个样本拼在一起会跨过 `</SOLUTION>` 边界，破坏思考结构学习 | `packing=False`，老老实实一个样本一个序列 |
| **swap 开启 + 不用 systemd-run --scope** | DGX Spark unified memory + swap 死亡螺旋会导致整机僵死、SSH 断、需要硬重启 | `sudo swapoff -a` + 训练命令包在 `MemoryMax=100G MemorySwapMax=0` 内 |
| **重新装 PyTorch / vllm 到现有 venv** | 会破坏 dgx-spark-setup 的兼容矩阵 | 直接复用 `/home/samuel/dgx-spark-setup/.venv`，只 `uv pip install` 增量包 |
## Stack Patterns by Variant
- 把 `max_seq_length` 升到 4096，`num_train_epochs=3`
- 仍然用 TRL+PEFT，不切 Unsloth（边际收益不抵切栈风险）
- 降到 `per_device_train_batch_size=2 / gradient_accumulation_steps=16`（effective batch 32 不变）
- 再不行：`lora_dropout=0.0` + 关 `bnb_4bit_use_double_quant`，省一点显存
- 降到 `max_workers=5`；保留断点续跑 JSONL；分批跑两天
- 加 `--imatrix`：用训练数据子集生成重要性矩阵：
- 然后 `llama-quantize --imatrix imatrix.dat tsc-cycle-4b-f16.gguf tsc-cycle-4b-q4_k_m-imat.gguf Q4_K_M`
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `torch>=2.9.0+cu130` | `transformers>=4.56.2` | bf16 在 GB10 原生支持；忽略 sm_120/121 警告 |
| `transformers==4.56.2` | `trl==0.22.2`, `peft>=0.15.1` | Unsloth Spark Dockerfile 三件套，社区验证 |
| `bitsandbytes==0.48.0` | `torch>=2.9 cu130 aarch64` | aarch64 wheel 有，sm_121 走 PTX JIT；不要升 1.x preview（继续 release 中） |
| `transformers>=4.51` | `Qwen3-4B-Thinking-2507` | 低于此版本 Qwen3 加载失败 |
| `openai>=1.50` | gpt-5.5 + `reasoning_effort` | `chat.completions.create(reasoning_effort="high")` 路径仍兼容 |
| `llama.cpp` (本机已 build, 含 Qwen3ForCausalLM 注册) | merged fp16 HF safetensors | `convert_hf_to_gguf.py:4551` 已注册；导出 fp16 → q4_K_M 已验证可行 |
## Reference Implementation 评估
### 权威源：`/home/samuel/dgx-spark-setup` + `/dgx-spark-training` skill
| 项 | 状态 |
|----|------|
| 训练框架 | **HF Transformers + TRL + PEFT + bitsandbytes**（与本项目推荐一致 ✓） |
| 环境复用 | `/home/samuel/dgx-spark-setup/.venv` 已存在的已知良好 venv，`/dgx-spark-training` skill 的 `scripts/setup_dgx_spark_env.sh` 默认模式直接 clone 这个 venv 到目标项目 |
| Python | 3.12（uv venv）|
| PyTorch | cu130 wheel（`https://download.pytorch.org/whl/cu130`）|
| Attention | **强制 SDPA**（`attn_implementation="sdpa"`）；不安装 upstream `flash-attn`（`libcudart.so.12` 失败）|
| Triton | 工作；需要 `TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas` |
| 内存防护 | swap 必须关；训练放进 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0`；SSH 加 OOM score adj |
| 验证脚本 | 项目目录下 `scripts/dgx_spark/verify.py` 与 `run_safe.sh` 已由 skill 自动注入 |
| 量化方向 | **GGUF（fp16 + q4_K_M）via llama.cpp**（本项目目标）|
## Sources
- [`/home/samuel/dgx-spark-setup/README.md`](file:///home/samuel/dgx-spark-setup/README.md) — HIGH（本机已知良好环境，逐项验证 PyTorch/transformers/peft/SDPA/swap-off）
- [`/home/samuel/dgx-spark-setup/pyproject.toml`](file:///home/samuel/dgx-spark-setup/pyproject.toml) — HIGH（torch+vllm+aarch64 marker pinning 模板）
- [`/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py`](file:///home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py) line 4551 — HIGH（本机已 build，`Qwen3ForCausalLM` 已注册）
- [`/home/samuel/projects/EvoProgTSC/llama.cpp/llama-quantize`](file:///home/samuel/projects/EvoProgTSC/llama.cpp/llama-quantize) — HIGH（`--help` 输出确认 Q4_K_M preset 15 可用）
- [`/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py`](file:///home/samuel/projects/EvoProgTSC/evoprog/llm/client.py) — HIGH（既有 OpenAI 重试/降级/结构化输出封装，直接复用）
- [`/home/samuel/.claude/skills/dgx-spark-training/SKILL.md`](file:///home/samuel/.claude/skills/dgx-spark-training/SKILL.md) — HIGH（训练栈唯一权威 skill；setup/verify/run_safe 完整工具链）
- [github.com/natolambert/dgx-spark-setup](https://github.com/natolambert/dgx-spark-setup) — HIGH（`/home/samuel/dgx-spark-setup` 的上游，CUDA 13/aarch64 配置权威源）
- ~~waybarrios/dgx-spark-finetune-llm~~ — **NOT USED**（用户明确排除）
- [Unsloth on DGX Spark — official docs](https://unsloth.ai/docs/blog/fine-tuning-llms-with-nvidia-dgx-spark-and-unsloth) — HIGH（`bitsandbytes==0.48.0`、`transformers==4.56.2`、`trl==0.22.2` 锚点版本）
- [build.nvidia.com/spark/unsloth/instructions](https://build.nvidia.com/spark/unsloth/instructions) — HIGH（NVIDIA 官方 Unsloth on Spark 教程，bitsandbytes aarch64 验证）
- [Qwen/Qwen3-4B-Thinking-2507 — HF model card](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507) — HIGH（`transformers>=4.51`、`Qwen3ForCausalLM` 架构、262k context、原生 `<think>` token id 151668）
- [Unsloth: Saving to GGUF](https://unsloth.ai/docs/basics/inference-and-deployment/saving-to-gguf) — HIGH（`q4_k_m` 命名、内部调用 llama.cpp 的 convert+quantize 链）
- [Qwen llama.cpp quantization guide](https://qwen.readthedocs.io/en/latest/quantization/llama.cpp.html) — HIGH（Q4_K_M + `--imatrix` 标准做法）
- [unslothai/unsloth Issue #3861](https://github.com/unslothai/unsloth/issues/3861) — MEDIUM（`save_pretrained_gguf` >50GB bug，4B 不触发但暴露其 wrapper 风险）
- [bitsandbytes-foundation/bitsandbytes Releases](https://github.com/bitsandbytes-foundation/bitsandbytes/releases) — HIGH（aarch64 wheel 状态：sm_75/80/90/100/Thor sm_110，sm_121 走 PTX JIT） 
- [vllm-project/vllm Issue #36821](https://github.com/vllm-project/vllm/issues/36821) — MEDIUM（确认 sm_121 aarch64 生态全面缺失，反向印证「不用 vllm/flash-attn」决策）
- [OpenAI: Using GPT-5.5](https://developers.openai.com/api/docs/guides/latest-model) — HIGH（`reasoning={"effort": "high"}` 参数语义、Batch API 与并发权衡）
- [unslothai/unsloth Issue #4867 — DGX Spark transformers patches](https://github.com/unslothai/unsloth/issues/4867) — MEDIUM（GPT-OSS 类需要 monkey-patch；Qwen3-Thinking 不属此类，但提示 Unsloth 路径有隐藏维护成本）
## Confidence Summary
| Recommendation | Confidence | Rationale |
|---|---|---|
| TRL+PEFT+bnb 而非 Unsloth | HIGH | dgx-spark-setup 已用同栈跑通 open-instruct；Unsloth Spark 路径有 transformers monkey-patch + GGUF wrapper 双重风险 |
| `bitsandbytes==0.48.0` aarch64 + sm_121 PTX JIT | HIGH | NVIDIA + Unsloth 双方官方文档锚定；社区 Issue 显示可工作 |
| QLoRA r=64 在 6h 内完成 4B SFT | HIGH | 0.6B SFT 47GB peak @ batch=8/seq=1024 推算 4B QLoRA @ batch=4/seq=2048 ~30–40GB，远低于 100GB 上限 |
| 本机 llama.cpp 直接 convert+quantize Qwen3-4B-Thinking | HIGH | `Qwen3ForCausalLM` 已注册（脚本第 4551 行）；Q4_K_M preset 已验证（`llama-quantize --help`） |
| 自定义思考标签训练稳定 | HIGH | MEMORY 已验证 tokenizer 行为；reality.log 已是此格式 |
| 复用 EvoProgTSC client + 加并发池 | HIGH | 现有重试/降级/结构化输出代码完整；只需新增 ThreadPoolExecutor + TSC schema + 硬约束 lint |
| q4_K_M 不会显著降级（不需要 imatrix） | MEDIUM | 4B + Q4_K_M 通常 OK，但思考链长输出对量化敏感；评测时务必同时跑 fp16 / q4_K_M 对比；崩塌时退到 imatrix |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
