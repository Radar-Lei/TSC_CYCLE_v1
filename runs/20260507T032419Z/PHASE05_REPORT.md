# Phase 5: Merge + GGUF Export 报告

**Run TS:** 20260507T032419Z
**生成时间:** 2026-05-07T09:30:00Z

## 1. Export 产物 (EXP-01/02/03)

| Artifact | Path | Size (MB) |
|---|---|---|
| merged_bf16 dir | runs/20260507T032419Z/merged_bf16 | — |
| GGUF bf16 | runs/20260507T032419Z/gguf/model.bf16.gguf | 7678 |
| GGUF q4_K_M | runs/20260507T032419Z/gguf/model.q4_K_M.gguf | 2381 |

注：`gguf_tokenizer_model = gpt2`，`gguf_pre_tokenizer = qwen2`；merge 路径走 bf16 reload base
（**非 4-bit base merge**），无 embedding resize（vocab=151936 与 Qwen3 base 一致）。

## 2. Tokenize Sanity (EXP-04)

| Tag | HF token ids | GGUF token ids | Match | Multi-token |
|---|---|---|---|---|
| `<start_working_out>` | [27, 2468, 81101, 6068, 29] | [27, 2468, 81101, 6068, 29] | ✓ | ✓ |
| `</end_working_out>`  | [522, 408, 81101, 6068, 29] | [522, 408, 81101, 6068, 29] | ✓ | ✓ |
| `<SOLUTION>`          | [18858, 45977, 29] | [18858, 45977, 29] | ✓ | ✓ |
| `</SOLUTION>`         | [522, 50, 45977, 29] | [522, 50, 45977, 29] | ✓ | ✓ |
| `<think>`             | [151667] | [13708, 766, 29] | ✗ | ✗ (HF 单 token) |
| `</think>`            | [151668] | [522, 26865, 29] | ✗ | ✗ (HF 单 token) |

- 全部 custom 标签 match: **True**
- 全部 custom 标签 multi-token: **True**
- 原生 `<think>`(151667) / `</think>`(151668) 在 HF tokenizer 中是单 token（added tokens），
  GGUF 由 BPE 拆为 sub-token —— 这是预期差异（自定义训练标签不依赖原生 think token，
  避免与预训练语义冲突，详见项目 MEMORY 关键教训）。EXP-04 仅要求自定义 4 个标签一致，**通过**。

## 3. Parity Test (EXP-05)

- 20 prompts (10 same-dist + 10 OOD) from `data/labeled.jsonl`，seed=42
  （`runs/20260507T032419Z/gguf/parity_prompts.jsonl`，md5=09fa4e6326722c37bad720dbfddc29db）
- n_predict=384, greedy (temp=0, top-k=1, seed=42)
- GGUF GPU 卸载 -ngl=99，ctx_size=4096，threads=4，timeout=600s
- llama-server 单加载（CUDA build `/home/samuel/llama.cpp/build/bin/llama-server`），
  HTTP `/completion` 每 prompt 一次（避免 per-prompt cold-start）

| Backend | Total wall (s) | parse_failures |
|---|---|---|
| HF bf16     | 134.5 | 0 |
| GGUF bf16   | 104.3 | 0 |
| GGUF q4_K_M | 48.9  | 0 |

- **GGUF bf16 vs HF bf16 整体 MAE:** 0.58 秒（量化无损：GGUF 格式本身保持决策一致）
- **q4_K_M vs HF bf16 整体 MAE:** **4.51 秒**
- **阈值:** 3.0 秒
- **状态:** **FLAG-imatrix-backlog**（mae_exceeded=True）

### Per-prompt MAE 分布（q4_K_M vs HF）

- 14/20: MAE ≤ 2.5s（量化几乎无影响）
- 3/20: MAE 4–10s（中度漂移）
- 3/20: MAE > 10s（q4 退化点），其中：
  - `33951e9d` (id): MAE 10.0 — `phase_4` HF=80, q4=49（缺尾偏短）
  - `dfb9ae1a` (ood): MAE 44.0 — `phase_3` HF=32, **q4=158** → **违反 max_green 硬约束**，
    q4 数值崩塌典型信号
  - `3378f32b` (ood): MAE 9.5 — `phase_1` HF=20, q4=45（首相位偏长）

## 4. Phase 5 收尾状态

- [x] EXP-01 merged_bf16 (vocab=151936, 无 resize)
- [x] EXP-02 GGUF bf16
- [x] EXP-03 GGUF q4_K_M (preset 15)
- [x] EXP-04 tokenize sanity 全绿（4 个自定义标签 HF↔GGUF 一致）
- [!] EXP-05 parity MAE = 4.51s **>** 3s（imatrix backlog 触发）

## 5. Backlog (imatrix 重量化预案)

q4_K_M MAE 4.51s 超 3s 阈值，且发现 OOD 样本 `dfb9ae1a` 输出 phase_3=158（违反 max_green 硬约束），
属典型 q4 退化点。按 plan 预案进入 backlog：

- 用 train split 子集（建议 ~256 条）跑 `llama-imatrix` 生成 `runs/{ts}/gguf/imatrix.dat`
- 重新量化：`llama-quantize --imatrix imatrix.dat model.bf16.gguf model.q4_K_M.imat.gguf Q4_K_M`
- 重跑 20-prompt parity，验证 MAE 是否回落到 ≤ 3s 且崩塌点（特别是 `dfb9ae1a`）消失
- 若 imatrix 仍不达标，回退 fp16 GGUF 部署或评估 Q5_K_M

Phase 6 评测会同时跑 HF bf16 / GGUF bf16 / GGUF q4_K_M 三 variant，可在 OOD val
硬约束满足率上对 q4 退化进一步定量。
