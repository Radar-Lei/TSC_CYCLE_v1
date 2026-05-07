"""GGUF vs HF tokenizer parity check for custom thinking tags (EXP-04).

Goal
----
After exporting the merged bf16 model to GGUF (fp16) and quantising to q4_K_M,
prove that the four custom multi-token tags

    <start_working_out>  </end_working_out>  <SOLUTION>  </SOLUTION>

tokenize **identically** under:
  1. The Hugging Face tokenizer of the merged checkpoint
     (`AutoTokenizer.from_pretrained(merged_hf)`).
  2. A BPE tokenizer rebuilt from the GGUF metadata using
     `gguf.GGUFReader` + `tokenizers.models.BPE`.

If the two diverge, the GGUF deployment will produce garbled output for any
training-format prompt — this is the cheapest pre-deploy guard we have.

Native single-token thinking tokens `<think>` (151667) and `</think>` (151668)
are also asserted (sanity: their HF ids must remain unchanged; they should NOT
appear in any custom-tag id sequence).

This module is the *only* sanctioned GGUF tokenizer probe path; the previously
considered llama-cli stdout regex fallback is intentionally not used (its
parsing surface is unreliable across binary versions).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Custom multi-token tags (must match tsc_cycle.prompt_builder).
CUSTOM_TAGS: list[str] = [
    "<start_working_out>",
    "</end_working_out>",
    "<SOLUTION>",
    "</SOLUTION>",
]
# Native Qwen3 single-token thinking tokens (must remain unchanged).
NATIVE_TAGS: list[str] = ["<think>", "</think>"]
NATIVE_THINK_OPEN_ID = 151667
NATIVE_THINK_CLOSE_ID = 151668

DEFAULT_MERGED_HF = "runs/20260507T032419Z/merged_bf16"
DEFAULT_GGUF = "runs/20260507T032419Z/gguf/model.q4_K_M.gguf"
DEFAULT_OUT = "runs/20260507T032419Z/gguf/tokenize_sanity.json"
DEFAULT_GGUF_PY = "/home/samuel/projects/EvoProgTSC/llama.cpp/gguf-py"


def _decode_str_list(field) -> list[str]:
    """Decode a GGUF string-array field to a list[str]."""
    return [
        bytes(field.parts[i]).decode("utf-8", errors="replace")
        for i in field.data
    ]


def _decode_scalar_str(field) -> str:
    """Decode a GGUF scalar string field."""
    # data is a 1-element index list pointing into parts.
    return bytes(field.parts[field.data[0]]).decode("utf-8", errors="replace")


def _fail(msg: str) -> None:
    print(f"[TOKENIZE-SANITY] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def build_hf_tokenizer(merged_hf: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(merged_hf)


def build_gguf_bpe_tokenizer(gguf_path: str, gguf_py_path: str) -> tuple[Any, dict[str, str]]:
    """Rebuild a tokenizers.Tokenizer (BPE) from GGUF metadata.

    Returns (tokenizer, meta) where meta carries
      {"model": <tokenizer.ggml.model>, "pre": <tokenizer.ggml.pre or "">}.
    """
    if gguf_py_path not in sys.path:
        sys.path.insert(0, gguf_py_path)
    import gguf  # type: ignore
    from tokenizers import Regex, Tokenizer, decoders, models, pre_tokenizers

    reader = gguf.GGUFReader(gguf_path)

    # GGUFReader.fields can be OrderedDict OR list depending on version — handle both.
    raw_fields = reader.fields
    if isinstance(raw_fields, dict):
        fields = dict(raw_fields)
    else:
        fields = {f.name: f for f in raw_fields}

    required = ["tokenizer.ggml.model", "tokenizer.ggml.tokens", "tokenizer.ggml.merges"]
    missing = [r for r in required if r not in fields]
    if missing:
        _fail(f"GGUF missing required tokenizer fields: {missing}")

    tokens = _decode_str_list(fields["tokenizer.ggml.tokens"])
    merges = _decode_str_list(fields["tokenizer.ggml.merges"])
    model_name = _decode_scalar_str(fields["tokenizer.ggml.model"])
    pre_name = (
        _decode_scalar_str(fields["tokenizer.ggml.pre"])
        if "tokenizer.ggml.pre" in fields
        else ""
    )

    vocab = {tok: i for i, tok in enumerate(tokens)}
    merge_pairs = [tuple(m.split(" ", 1)) for m in merges if " " in m]

    bpe = Tokenizer(models.BPE(vocab=vocab, merges=merge_pairs, fuse_unk=False))
    # Replicate Qwen3's HF tokenizer.json pre_tokenizer Sequence:
    #   1) GPT-2 / qwen2 split regex (Isolated behaviour)
    #   2) ByteLevel(add_prefix_space=False, use_regex=False)
    # NOTE: a single ByteLevel(use_regex=True) does NOT match — its built-in
    # regex differs subtly from Qwen2's (e.g. handling of leading-non-space-non-
    # alnum + letters), causing token boundaries like '_working' (81101) to be
    # missed and falling back to '_'+'working'. Mirroring the Sequence exactly
    # is the only path that reproduces HF tokenization on byte-identical vocab.
    qwen2_split_pattern = (
        r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
        r"|[^\r\n\p{L}\p{N}]?\p{L}+"
        r"|\p{N}"
        r"| ?[^\s\p{L}\p{N}]+[\r\n]*"
        r"|\s*[\r\n]+"
        r"|\s+(?!\S)"
        r"|\s+"
    )
    bpe.pre_tokenizer = pre_tokenizers.Sequence(
        [
            pre_tokenizers.Split(
                pattern=Regex(qwen2_split_pattern),
                behavior="isolated",
                invert=False,
            ),
            pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
        ]
    )
    bpe.decoder = decoders.ByteLevel()

    return bpe, {"model": model_name, "pre": pre_name}


def encode_hf(tokenizer, text: str) -> list[int]:
    return list(tokenizer.encode(text, add_special_tokens=False))


def encode_gguf(bpe, text: str) -> list[int]:
    return list(bpe.encode(text, add_special_tokens=False).ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merged-hf", default=DEFAULT_MERGED_HF)
    parser.add_argument("--gguf", default=DEFAULT_GGUF)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--gguf-py-path", default=DEFAULT_GGUF_PY)
    args = parser.parse_args()

    merged_hf = Path(args.merged_hf)
    gguf_path = Path(args.gguf)
    out_path = Path(args.out)

    if not merged_hf.exists():
        _fail(f"merged HF dir not found: {merged_hf}")
    if not gguf_path.exists():
        _fail(f"gguf file not found: {gguf_path}")

    hf_tok = build_hf_tokenizer(str(merged_hf))
    bpe, gmeta = build_gguf_bpe_tokenizer(str(gguf_path), args.gguf_py_path)

    tag_records: list[dict[str, Any]] = []
    all_tags = CUSTOM_TAGS + NATIVE_TAGS
    for tag in all_tags:
        hf_ids = encode_hf(hf_tok, tag)
        gguf_ids = encode_gguf(bpe, tag)
        tag_records.append(
            {
                "tag": tag,
                "hf_ids": hf_ids,
                "gguf_ids": gguf_ids,
                "match": hf_ids == gguf_ids,
                "is_multi_token": len(hf_ids) > 1,
            }
        )

    custom_records = [r for r in tag_records if r["tag"] in CUSTOM_TAGS]
    native_records = [r for r in tag_records if r["tag"] in NATIVE_TAGS]

    all_custom_match = all(r["match"] for r in custom_records)
    all_custom_multi_token = all(r["is_multi_token"] for r in custom_records)

    native_open = next(r for r in native_records if r["tag"] == "<think>")
    native_close = next(r for r in native_records if r["tag"] == "</think>")

    payload: dict[str, Any] = {
        "merged_hf": str(merged_hf),
        "gguf": str(gguf_path),
        "gguf_tokenizer_model": gmeta["model"],
        "gguf_pre_tokenizer": gmeta["pre"] or None,
        "tags": tag_records,
        "all_custom_match": all_custom_match,
        "all_custom_multi_token": all_custom_multi_token,
        "native_think_id": NATIVE_THINK_OPEN_ID,
        "native_think_close_id": NATIVE_THINK_CLOSE_ID,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    # Hard assertions.
    if not all_custom_match:
        bad = [r["tag"] for r in custom_records if not r["match"]]
        _fail(f"custom tags hf!=gguf: {bad}; wrote diagnostic to {out_path}")
    if not all_custom_multi_token:
        bad = [r["tag"] for r in custom_records if not r["is_multi_token"]]
        _fail(f"custom tags not multi-token (in vocab as added tokens): {bad}")
    if native_open["hf_ids"] != [NATIVE_THINK_OPEN_ID]:
        _fail(f"<think> hf_ids={native_open['hf_ids']} expected [{NATIVE_THINK_OPEN_ID}]")
    if native_close["hf_ids"] != [NATIVE_THINK_CLOSE_ID]:
        _fail(f"</think> hf_ids={native_close['hf_ids']} expected [{NATIVE_THINK_CLOSE_ID}]")

    print(f"[TOKENIZE-SANITY] OK -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
