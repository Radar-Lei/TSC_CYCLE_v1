# OOD Specification — TSC-CYCLE Phase 2

**Version:** v1
**Date:** 2026-05-07

## 目的

`reality.log` 仅有 2 个路口、426 个 prompt、相位数集中在 {3,4,5}，min/max_green 集中在少数几个模式（`(20,45)`, `(50,80)`, `(45,80)`, `(30,80)`, `(15,30)`）。学生模型若只在同分布合成数据上训练，会过拟合到这些模式。OOD val split 必须考验：模型从硬约束出发，**而非记忆模式**。

## OOD 维度（必须至少打破其中一项）

### 1. Phase Count 扩展
- **同分布**: 相位数 ∈ {3, 4, 5}（按 reality.log 频率加权）
- **OOD**: 相位数 ∈ {2, 6, 7, 8}（reality.log 完全没出现过）

### 2. Range 模式打破（min/max 组合）
- **同分布**: `(min, max)` 从 `dist_prior.range_modes_top` 前 10 加权采样
- **OOD**: 至少满足下列之一
  - 全新 min: min_green ∈ {5, 10, 90, 100, 120}（log 内 min 范围 ≈ [15, 50]）
  - 全新 max: max_green ∈ {25, 35, 60, 110, 150}（log 内 max 范围 ≈ [25, 80]）
  - 全新组合: `(min, max)` 不出现在 log 任何一个相位中（cross-product 反查）
  - 极窄区间: max - min < 5（log 内最窄约为 15）
  - 极宽区间: max - min > 80（log 内最宽约为 65）

### 3. 饱和度区间
- **同分布**: `pred_saturation` ∈ log 经验 5%–95% 区间
- **OOD**: `pred_saturation` 偏到 ≤ 0.001 或 ≥ 0.5（log 实测大多在 [0.005, 0.15]）

### 4. pred_wait 离群
- **同分布**: `pred_wait` ∈ log 经验 5%–95% 区间
- **OOD**: `pred_wait` ≤ 0.05 或 ≥ 50（log 实测多在 [0.4, 5]）

### 5. capacity 极值
- **OOD**: `capacity` ∈ {1, 5, 200, 500}（log 多在 [10, 100]）

### 6. 业务相关性打破
- 在 reality.log 里，高 `pred_saturation` 的相位往往伴随高 `pred_wait`（因为 sat = wait/cap）。OOD 故意打破这一相关性：随机独立采样 wait 与 sat。

## 采样策略

每个 OOD 样本必须**至少打破一项 OOD 维度**。`sample_inputs.py` 实现：
1. 从 dist_prior 采同分布作 base
2. 随机选择 1–2 个 OOD 维度激活，对应字段从 OOD 分布替换
3. 计算 `sample_id = sha256(canonical_input)`，确保唯一

## 验证

`scripts/dist_check.py`：
- 同分布集对每个数值字段做 KS test vs reality.log 经验分布，要求 p > 0.05
- OOD 集对每个数值字段做 KS test vs reality.log 经验分布，要求至少一维 p < 0.01（不必所有维都 OOD，但每个样本都得有打破点）
- 报告写入 `data/dist_check_report.md`

## Trivial 样本标记

若 `min_green == max_green` 对所有相位都成立 → `trivial=True`（决策只能是 min=max 唯一值）。该样本 EVL 时单独排除以免高估硬约束满足率。
