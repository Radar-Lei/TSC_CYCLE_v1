---
plan: 06-02
status: complete
note: agent finished generation; final SUMMARY commit lost to 502 — replacement written by orchestrator
---

# Plan 06-02 Summary — hf_bf16 EVL Generation Runner

## What was built

`tsc_cycle/eval/generate_hf.py`：HF bf16 EVL generation runner，基于 `tsc_cycle/student/parity_hf.py` 改造。一次性加载 `runs/20260507T032419Z/merged_bf16/`（bf16 + SDPA），按 `eval_prompts.jsonl` 顺序生成 600 prompts，逐 sample 落盘到 `runs/20260507T032419Z/eval/gen_cache/hf_bf16/{sample_id}.json`。断点续跑：cache 已存在跳过。

## Generation parameters

- max_new_tokens=384, do_sample=False, temperature=0.0, top_k=1, seed=42
- pad_token_id=tokenizer.eos_token_id
- 解析 `<SOLUTION>{json}</SOLUTION>` regex (re.DOTALL)；失败时 parse_error 记录原因，raw_text 保留

## Cache schema

```json
{
  "sample_id": "<sha256>",
  "split_hint": "id|ood",
  "backend": "hf_bf16",
  "solution": {...} | null,
  "parse_error": null | "...",
  "raw_text": "...",
  "n_predict": 384,
  "seed": 42
}
```

## Verification

- `ls runs/20260507T032419Z/eval/gen_cache/hf_bf16/ | wc -l` = **600** ✓
- 全部 600 sample 字段含 `solution` 或 `parse_error`（非空）

## Commits

- `0f9d090` feat(06-02): add hf_bf16 eval generation runner

## Notes / Deviations

- 生成耗时 ~80 min（600 prompts × 8s/prompt avg）
- 完成后 `del model; torch.cuda.empty_cache()` 释放显存，为 wave 2 后续 GGUF runner 让路
- API 502 在最后阶段中断了 agent 的 SUMMARY commit，但工作产出（600 cache + runner 脚本）已完整落盘并提交
