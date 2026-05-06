"""Run manifest writer — anchors every stage's outputs to git sha + config hash."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex


def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.getcwd(), text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()
    except Exception:
        return "unknown"


def now_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_dir(run_id: str | None = None, base: str = "runs") -> Path:
    rid = run_id or now_run_id()
    p = Path(base) / rid
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_manifest(run_dir: Path, config: dict[str, Any], stages: dict[str, str]) -> Path:
    payload = {
        "git_sha": git_sha(),
        "config_hash": sha256_hex(canonical_json(config)),
        "config": config,
        "stages": stages,  # e.g. {"data_gen": "complete", "teacher": "in_progress"}
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = run_dir / "manifest.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def update_stage(run_dir: Path, stage: str, status: str, **extra: Any) -> None:
    p = run_dir / "manifest.json"
    if not p.exists():
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("stages", {})[stage] = status
    if extra:
        data.setdefault("stage_details", {})[stage] = extra
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
