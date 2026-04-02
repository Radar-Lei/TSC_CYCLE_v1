# Milestones

## v1.1 简化版 GRPO 训练 (Shipped: 2026-04-02)

**Delivered:** 交付了与旧版 GRPO 隔离的简化版 reward、数据生成与 Docker 训练入口。

**Phases completed:** 2 phases, 2 plans, 4 tasks

**Key accomplishments:**

- 新增 `src/grpo_simple/rewards.py`，用饱和度比例 reward 取代 SUMO 仿真依赖
- 新增 `tests/test_grpo_simple_rewards.py`，覆盖命中、偏离、越界与格式错误
- 新增 `src/scripts/generate_grpo_simple_data.py` 与 `docker/grpo_simple_data.sh`，直接从 `outputs/data/train.jsonl` 生成 16,788 条 GRPO-simple 数据
- 新增 `src/grpo_simple/train.py` 与 `docker/grpo_simple_train.sh`，把训练入口和输出目录隔离到 `outputs/grpo_simple/`

**Stats:**

- 6 个核心代码/脚本文件新增，1 个配置文件扩展
- 806 行简化版 GRPO 相关代码与测试
- 2 phases, 2 plans, 4 tasks
- 1 天内从里程碑定义到交付

**What's next:** 将简化版 GRPO 接回 benchmark，并评估与完整版 SUMO reward 的差异。

---

## v1.0 GLM-5 SFT 数据生成 (Shipped: 2026-04-01)

**Phases completed:** 3 phases, 7 plans, 10 tasks

**Key accomplishments:**

- GLM-5 API 客户端: OpenAI 兼容接口, 4 并发 ThreadPoolExecutor, 指数退避重试 (2s/4s/8s), max_tokens=8192
- StratifiedSampler 按 (tl_id, 饱和度桶) 二维分层从 16788 条 train.jsonl 中抽样，覆盖全部 34 个交叉口和 3 个饱和度级别
- GLM-5 prompt 构建器复用 PromptBuilder 并追加 ~500 token think 链引导，输出解析器提取标签内容并校验相位顺序/绿灯范围/整数约束
- BatchGenerator 编排器: ThreadPoolExecutor 并发调用 GLM-5，含断点续传、约束校验重试(3次)、逐条追加写入和实时进度显示
- results.jsonl 到 sft_train.jsonl 的组装脚本，支持 BatchGenerator 双格式兼容和 status 过滤

### Known Gaps

以下需求因 Docker 环境任务 deferred 未在里程碑期间完成，需手动执行：

- **TRAIN-01**: Docker SFT 训练验证 (`./docker/sft_train.sh`)
- **TRAIN-02**: 训练 loss 曲线检查
- **EXPORT-01**: Q4_K_M GGUF 导出 (`./docker/convert_gguf.sh`)
- **EXPORT-02**: Q8_0 GGUF 导出
- **EXPORT-03**: F16 GGUF 导出

---
