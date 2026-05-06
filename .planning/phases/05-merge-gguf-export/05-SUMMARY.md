# Phase 5 SUMMARY — Merge + GGUF Export (script-ready)

**Status:** Script ready; blocked on Phase 4 adapter output.

## Implementation
- `tsc_cycle/student/export_gguf.py`
  - reload Qwen3-4B-Thinking-2507 base in **bf16** (not 4-bit); attach LoRA via `PeftModel.from_pretrained`; `merge_and_unload`
  - Save merged HF dir; tokenizer_check post-merge
  - Convert via `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py --outtype bf16` (Qwen3ForCausalLM registered line ~4551)
  - Quantize via `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-quantize <bf16> <q4_K_M> Q4_K_M`
- `tsc_cycle/eval/parity.py` — 20 OOD prompts, greedy seed=42, MAE q4 vs HF bf16; gate ≤ 3.0
