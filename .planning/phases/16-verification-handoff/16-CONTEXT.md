# Phase 16 Context: Verification & Handoff

## Goal

Reproducer and maintainer can verify the cleaned repository still reproduces the shipped v4.0 evidence path.

## Scope

Phase 16 is a final handoff verification phase for v4.1. It does not retrain, regenerate datasets, run model inference, or add new model capability. It proves the retained v4.0 Qwen3-4B 9k package remains complete after cleanup.

## Required Checks

- Validate `reproduction/v4.0-qwen3-4b-9k-manifest.json` against disk.
- Run the cleanup/reproduction pytest subset without writing pytest cache or Python bytecode.
- Confirm required v4 source/evidence paths exist.
- Confirm non-v4 clutter targeted by Phase 15 remains absent.
- Leave a concise handoff summary for the maintainer.
