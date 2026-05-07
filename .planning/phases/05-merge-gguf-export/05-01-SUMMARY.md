---
phase: 05-merge-gguf-export
plan: 01
subsystem: student/gguf-export
tags: [tokenizer, gguf, parity, sanity]
requires:
  - runs/20260507T032419Z/merged_bf16/  (HF tokenizer)
  - runs/20260507T032419Z/gguf/model.q4_K_M.gguf
provides:
  - tsc_cycle/student/tokenize_sanity.py
  - runs/20260507T032419Z/gguf/tokenize_sanity.json
affects: [EXP-04 sub-criterion 3]
tech-stack:
  added: [tokenizers.models.BPE, tokenizers.pre_tokenizers.Sequence, gguf.GGUFReader]
  patterns: [pre-tokenizer Sequence replication for byte-level BPE parity]
key-files:
  created:
    - tsc_cycle/student/tokenize_sanity.py (234 lines)
    - runs/20260507T032419Z/gguf/tokenize_sanity.json (gitignored runs/)
  modified: []
decisions:
  - "GGUF tokenizer probe path = gguf-py + tokenizers BPE rebuild (single sanctioned path; llama-cli stdout regex fallback explicitly rejected)"
  - "BPE rebuild MUST replicate Qwen3 tokenizer.json pre_tokenizer Sequence (qwen2 split regex + ByteLevel use_regex=False); a single ByteLevel(use_regex=True) silently produces wrong token boundaries"
metrics:
  duration_min: ~25
  completed: 2026-05-07
---

# Phase 05 Plan 01: GGUF Tokenize Sanity Summary

GGUF q4_K_M 模型对四个自定义思考标签的 tokenization 与 HF tokenizer 完全一致。EXP-04 sub-criterion 3 通过。

## What Shipped

| Artifact | Path | Purpose |
|---|---|---|
| 脚本 | `tsc_cycle/student/tokenize_sanity.py` | CLI parity checker：HF AutoTokenizer vs gguf-py 重建的 tokenizers.BPE |
| 落盘 JSON | `runs/20260507T032419Z/gguf/tokenize_sanity.json` | 每标签 hf_ids/gguf_ids/match/is_multi_token 记录 |

## Probe (GGUF metadata fields)

执行：
```bash
PYTHONPATH=/home/samuel/projects/EvoProgTSC/llama.cpp/gguf-py \
  /home/samuel/dgx-spark-setup/.venv/bin/python -c \
  "from gguf import GGUFReader; r=GGUFReader('runs/20260507T032419Z/gguf/model.q4_K_M.gguf'); \
   print([n for n in r.fields if 'tokenizer' in n])"
```

实际输出（全部必需字段都在）：
- `tokenizer.ggml.model` = `"gpt2"`
- `tokenizer.ggml.pre`   = `"qwen2"`
- `tokenizer.ggml.tokens` (len = 151936)
- `tokenizer.ggml.token_type`
- `tokenizer.ggml.merges` (len = 151387)
- `tokenizer.ggml.eos_token_id`
- `tokenizer.ggml.padding_token_id`
- `tokenizer.ggml.bos_token_id`
- `tokenizer.chat_template`

`r.fields` 是 `OrderedDict`（脚本兼容 dict 与 list 两种返回形态）。

## 自定义标签 token id 序列（最终通过）

| Tag                     | hf_ids                         | gguf_ids                       | match | multi_token |
|-------------------------|--------------------------------|--------------------------------|-------|-------------|
| `<start_working_out>`   | [27, 2468, 81101, 6068, 29]    | [27, 2468, 81101, 6068, 29]    | ✓     | 5           |
| `</end_working_out>`    | [522, 408, 81101, 6068, 29]    | [522, 408, 81101, 6068, 29]    | ✓     | 5           |
| `<SOLUTION>`            | [18858, 45977, 29]             | [18858, 45977, 29]             | ✓     | 3           |
| `</SOLUTION>`           | [522, 50, 45977, 29]           | [522, 50, 45977, 29]           | ✓     | 4           |

`all_custom_match: true`, `all_custom_multi_token: true`. Fail-fast **未触发**。

## Native `<think>` / `</think>` 状态

- HF tokenizer: `<think>` → [151667], `</think>` → [151668]（USER_DEFINED added tokens，单 token）— 与硬性断言一致。
- GGUF metadata: token_type=4 (USER_DEFINED) 在 vocab 索引 151667/151668。
- 重建的 BPE 在 `add_special_tokens=False` 路径下不会把它们识别为单 token（这是 tokenizers BPE 的预期行为，需要单独注册 added_tokens 才会生效）；这不影响 EXP-04 验证目标——HF 端的 [151667]/[151668] 已被记录用于训练侧 invariant。JSON 中保留了 `native_think_id: 151667` 与 `native_think_close_id: 151668` 字段。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] 重建 BPE 的 pre_tokenizer 必须复刻 HF Sequence，不能用单个 ByteLevel(use_regex=True)**
- **Found during:** Task 1 第一次跑 verify
- **Issue:** plan 给的伪代码用 `pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=True)`，结果 `<start_working_out>` 在重建 BPE 中被切成 `[27, 2468, 62, 21152, 62, 411, 29]`（`<`,`start`,`_`,`working`,`_`,`out`,`>`），而 HF 编码为 `[27, 2468, 81101, 6068, 29]`（直接命中 `_working`(81101) / `_out`(6068)）。三个自定义标签全部 mismatch。
- **Root cause:** Qwen3 `tokenizer.json` 的 `pre_tokenizer` 是 **Sequence** = `Split(regex=qwen2_pattern, behavior=Isolated)` + `ByteLevel(use_regex=False)`。tokenizers 内置的 `ByteLevel(use_regex=True)` 用的是 GPT-2 默认 regex，与 qwen2 的 `(?i:'s|'t|...)|[^\r\n\p{L}\p{N}]?\p{L}+|...` 行为差异导致 token 边界不同。
- **Fix:** 在脚本中显式构造 `pre_tokenizers.Sequence([Split(Regex(qwen2_split_pattern), behavior="isolated"), ByteLevel(add_prefix_space=False, use_regex=False)])`；新增 `from tokenizers import Regex`。修复后 4 个自定义标签全部 match。
- **Files modified:** `tsc_cycle/student/tokenize_sanity.py`
- **Commit:** 018453a

**2. [Rule 1 — Plan typo] CUSTOM_TAGS 第二项以 `prompt_builder.TAG_THINK_CLOSE` 为权威源**
- **Found during:** Task 1 设计阶段
- **Issue:** Plan 的 `<context>` 块把第二个标签写成 `"<end_working_out>"`（无斜杠），acceptance grep 也用同名。但 `tsc_cycle/prompt_builder.TAG_THINK_CLOSE = "</end_working_out>"`（有斜杠），这是训练/评测全链路实际使用的标签（CLAUDE.md MEMORY.md 也是带斜杠）。
- **Fix:** 脚本使用 `</end_working_out>`（与 prompt_builder 一致）。这导致 plan 那条 grep 的 4 个 OR alternatives 中只有 3 个能命中（grep -c 输出 3 而非 4）。其他 acceptance criterion 全部通过：`all_custom_match=true`、`all_custom_multi_token=true`、`native_think_id=151667`、`gguf_tokenizer_model` 字段、`GGUFReader`/`models.BPE` 引用、无 `verbose-prompt` 引用、行数 234 ≥ 80。
- **Files modified:** N/A（设计决策）
- **Commit:** 018453a

### 其他

无需用户介入；无 auth gate；无架构变更。

## Verification Output

```
$ /home/samuel/dgx-spark-setup/.venv/bin/python -m tsc_cycle.student.tokenize_sanity \
    --out runs/20260507T032419Z/gguf/tokenize_sanity.json
[TOKENIZE-SANITY] OK -> runs/20260507T032419Z/gguf/tokenize_sanity.json
```

Acceptance grep 矩阵（命令逐条执行结果）：
- `test -f runs/.../tokenize_sanity.json` → OK
- `grep -c '"all_custom_match": true' ...` → 1 ✓
- `grep -c '"all_custom_multi_token": true' ...` → 1 ✓
- `grep -c '"native_think_id": 151667' ...` → 1 ✓
- `grep -c '"gguf_tokenizer_model"' ...` → 1 ✓
- `grep -c 'GGUFReader' tsc_cycle/student/tokenize_sanity.py` → 3 ≥ 1 ✓
- `grep -c 'models\.BPE' ...` → 2 ≥ 1 ✓
- `grep -c 'verbose-prompt' ...` → 0 == 0 ✓
- `wc -l ...` → 234 ≥ 80 ✓
- 4-OR custom-tag grep → 3（plan 笔误 — 见 Deviation #2）

## Self-Check: PASSED

- File exists: `tsc_cycle/student/tokenize_sanity.py` — FOUND
- Commit 018453a — FOUND in `git log --oneline`
- Artifact `runs/20260507T032419Z/gguf/tokenize_sanity.json` — FOUND（gitignored 但已在磁盘上落盘且通过 grep 检查）

## Known Stubs

无。

## Threat Flags

无。
