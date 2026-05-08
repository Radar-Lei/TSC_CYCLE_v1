from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_SAFE = ROOT / "scripts" / "dgx_spark" / "run_safe.sh"


def test_run_safe_fails_fast_when_noninteractive_systemd_run_sudo_is_unavailable(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    (fake_bin / "awk").write_text("#!/bin/sh\necho 128\n", encoding="utf-8")
    (fake_bin / "awk").chmod(0o755)

    (fake_bin / "sudo").write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-n\" ] && [ \"$2\" = \"/usr/bin/systemd-run\" ] && [ \"$3\" = \"--version\" ]; then\n"
        "  echo 'sudo: a password is required' >&2\n"
        "  exit 1\n"
        "fi\n"
        "echo 'UNSAFE systemd-run attempted without preflight' >&2\n"
        "exit 42\n",
        encoding="utf-8",
    )
    (fake_bin / "sudo").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CUDA_HOME"] = str(tmp_path / "cuda")

    result = subprocess.run(
        [str(RUN_SAFE), "100G", "--", "true"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "UNSAFE systemd-run attempted" not in result.stderr
    assert "non-interactive sudo" in result.stderr
    assert "NOPASSWD" in result.stderr


def test_run_safe_accepts_systemd_run_only_sudoers_rule(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    (fake_bin / "awk").write_text("#!/bin/sh\necho 128\n", encoding="utf-8")
    (fake_bin / "awk").chmod(0o755)

    (fake_bin / "sudo").write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-n\" ] && [ \"$2\" = \"/usr/bin/systemd-run\" ] && [ \"$3\" = \"--version\" ]; then\n"
        "  exit 0\n"
        "fi\n"
        "case \"$*\" in\n"
        "  *'systemd-run --scope'*) echo 'systemd-run launched' >&2; exit 0 ;;\n"
        "esac\n"
        "echo \"unexpected sudo invocation: $*\" >&2\n"
        "exit 43\n",
        encoding="utf-8",
    )
    (fake_bin / "sudo").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CUDA_HOME"] = str(tmp_path / "cuda")

    result = subprocess.run(
        [str(RUN_SAFE), "100G", "--", "true"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "systemd-run launched" in result.stderr
