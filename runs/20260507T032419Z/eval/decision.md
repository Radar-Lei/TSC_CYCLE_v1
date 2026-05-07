# Phase 6 Deployment Decision

**GO/NO-GO:** GO
**Threshold:** q4_K_M_ood_lint_rate / hf_bf16_ood_lint_rate >= 0.95
**Computed ratio:** 0.9933

## Numbers

| Backend | OOD lint_ok rate (non-trivial) | n |
|---|---|---|
| hf_bf16 | 0.9933 | 300 |
| gguf_bf16 | 0.9933 | 300 |
| gguf_q4_k_m | 0.9867 | 300 |

OOD MAE (mean): hf_bf16=7.936s, gguf_bf16=7.670s, gguf_q4_k_m=7.846s

## Key Findings

- **结构稳定性**：q4_K_M 在 600-prompt 评测全集上 parse_error=0，思考标签闭合 100%；Phase-5 parity 子集（20 prompt）上观察到的 dfb9ae1a 崩塌信号在全集上没有泛化。
- **教师 MAE 退化**：q4_K_M vs gguf_bf16 OOD MAE Δ = +0.176s，远低于 plan 06-05 设定的 3s 阈值。
- **硬约束退化**：q4_K_M OOD lint_ok = 98.7% vs hf_bf16 OOD lint_ok = 99.3%（Δ = -0.67 pp）；ratio = 0.9933。
- **Reasoning 引用质量**：q4_K_M `full` tier 在 OOD 上反而高于 bf16 后端（见 report.md `Reasoning Quality` 节）。

## Downstream Action

- ✅ 部署 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (~2.4 GB) 至 EvoProgTSC TSC 决策端点。
- 保留 `runs/20260507T032419Z/gguf/model.bf16.gguf` 作为 fallback（如生产观测显示退化）。
- **Future enhancement (非阻塞)**：imatrix 校准重量化作为 backlog，进入 v2 `Q-02`；触发条件 = 生产观测到 OOD lint_ok < 95% 或 MAE 漂移 > 3s。
