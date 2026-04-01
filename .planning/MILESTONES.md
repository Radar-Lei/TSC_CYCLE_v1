# Milestones

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
