# Requirements: TSC-CYCLE v4.2

**Defined:** 2026-05-18
**Core Value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近正确的饱和度-绿灯策略 —— 不是过拟合旧教师标签或 reality.log。

## v4.2 Requirements

### Audit

- [x] **AUDIT-01**: Maintainer can quantify how often existing v4 teacher labels assign `final == max_green` when `pred_saturation < 1.0`, broken down by saturation bands and split/source.
- [x] **AUDIT-02**: Maintainer can inspect representative failure examples from both `data/v4/phase8/labeled_merged.jsonl` and `reality_test.log`, including sample id, phase id, saturation, min/max green, final green, and violation category.

### Policy

- [x] **POLICY-01**: Maintainer can run a saturation policy gate that classifies each phase decision against the intended bands: `sat < 0.2` near min, `0.2 <= sat < 0.6` interpolated, `0.6 <= sat < 1.0` high but not max, and `sat >= 1.0` allowed max.
- [x] **POLICY-02**: Maintainer can fail data, model evaluation, or replay outputs when low-saturation max-green behavior exceeds configured thresholds.
- [x] **POLICY-03**: Final deployment prompts remain unchanged from the v4 inference protocol and do not explicitly include the saturation band rule; the rule is used only for offline audit, data construction, training validation, and evaluation gates.

### Data

- [ ] **DATA-01**: Maintainer can build a calibrated v4.2 training dataset by filtering or relabeling v4 examples that violate the saturation policy gate while preserving protocol format and hard-constraint validity.
- [ ] **DATA-02**: Maintainer can review a data reconstruction report showing source counts, rejected/relabelled counts, policy-pass rates, hard-constraint pass rates, and dataset hashes/splits.

### Training

- [ ] **TRAIN-01**: Maintainer can retrain `Qwen/Qwen3-4B-Thinking-2507` with the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack and without introducing a new base model or training framework.
- [ ] **TRAIN-02**: Maintainer can export the calibrated model to merged HF plus GGUF fp16 and q4_K_M artifacts with reproducible paths, hashes, and export reports.

### Evaluation

- [ ] **EVAL-01**: Maintainer can evaluate the calibrated model on hard constraints, output protocol, and saturation policy gates, with the old teacher-MAE metric demoted or replaced so it no longer rewards reproducing bad teacher labels.
- [ ] **EVAL-02**: Maintainer can replay `reality.log` with the calibrated q4_K_M model to generate a new `reality_test.log` that passes parse, lint, protocol, and saturation policy gates.
- [ ] **EVAL-03**: Maintainer can compare v4.0 and v4.2 outputs and confirm that low-saturation max-green failures are removed or reduced to the approved threshold without regressing hard-constraint validity.

## Future Requirements

### Deployment

- **DEPLOY-01**: Maintainer can integrate the calibrated GGUF artifact into an external TSC deployment endpoint and validate end-to-end behavior.

### Experiments

- **EXP-01**: Maintainer can run thinking on/off ablations to quantify the marginal value of explicit reasoning.
- **EXP-02**: Maintainer can evaluate imatrix or q5_K_M fallback if later deployment discovers q4_K_M quantization sensitivity.

## Out of Scope

| Feature | Reason |
|---------|--------|
| EvoProgTSC integration | v4.2 is only about this project’s model/data calibration; user clarified it has nothing to do with Evo. |
| Changing final deployment prompt | The calibrated model must learn the policy through data/training; inference prompt must not explicitly expose the saturation bands. |
| New base model | Current route stays on `Qwen/Qwen3-4B-Thinking-2507`. |
| New training stack | Existing DGX Spark-safe QLoRA path is already validated and should be reused. |
| thinking on/off ablation | Useful later, but not part of this calibration milestone. |
| imatrix/q5_K_M fallback | Deferred unless q4_K_M calibration or deployment reveals quantization sensitivity. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 17 | Complete in 17-01 |
| AUDIT-02 | Phase 17 | Complete in 17-01 |
| POLICY-01 | Phase 17 | Complete in 17-01 |
| POLICY-02 | Phase 17 | Complete in 17-02 |
| POLICY-03 | Phase 17 | Complete in 17-02 |
| DATA-01 | Phase 18 | Complete in 18-01 |
| DATA-02 | Phase 18 | Complete in 18-01 |
| TRAIN-01 | Phase 19 | Pending |
| TRAIN-02 | Phase 19 | Pending |
| EVAL-01 | Phase 20 | Pending |
| EVAL-02 | Phase 20 | Pending |
| EVAL-03 | Phase 20 | Pending |

**Coverage:**
- v4.2 requirements: 12 total
- Mapped to phases: 12
- Completed: 5
- Unmapped: 0

---
*Requirements defined: 2026-05-18*
*Last updated: 2026-05-18 after Phase 17 Plan 02 execution*
