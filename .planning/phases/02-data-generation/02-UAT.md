---
status: complete
phase: 02-data-generation
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md]
started: 2026-02-08T12:00:00Z
updated: 2026-02-08T13:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 仿真时长配置为 3600 秒
expected: config.json 中 sim_duration 为 3600，DaySimulator.sim_end 默认值为 3600，仿真运行 3600 秒
result: pass

### 2. 场景发现失败时立即报错
expected: 如果场景目录中缺少 .sumocfg 或 .net.xml 文件，程序立即报错停止，不会静默跳过
result: pass

### 3. 交叉口级并行执行
expected: 数据生成以交叉口为单位并行（ProcessPoolExecutor），任一交叉口失败时 cancel 其他任务并 shutdown（fail-fast）
result: pass

### 4. --scenarios 场景过滤参数
expected: 运行 generate_training_data.py 时可通过 --scenarios 参数指定场景子集，仅处理指定场景
result: pass

### 5. CoT 格式 SFT 训练数据生成
expected: 原始 JSONL 数据经过 convert_to_sft_format() 转换为 SFT chat 格式（system/user/assistant 三角色），assistant 消息包含 <think>\n\n</think> 空占位标签 + JSON 数组输出，保存到 outputs/sft/ 目录
result: pass

### 6. 智能饱和度插值计算
expected: final 绿灯时间基于 pred_saturation 计算：饱和度 > 1.0 → max_green；饱和度 < 0.5 → min_green；0.5-1.0 之间线性插值
result: pass

### 7. 动态首绿相位检测
expected: CycleDetector 从 phase_config 提取首绿相位 phase_index（而非硬编码 0），tl_id 缺失时回退默认值 0
result: skipped
reason: 内部逻辑无法从 data.sh 运行结果手动观察

## Summary

total: 7
passed: 6
issues: 0
pending: 0
skipped: 1

## Gaps

[none]
