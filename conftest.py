"""Pytest configuration for TSC_CYCLE project.

This file configures the Python path so that TSC_CYCLE modules can be imported
during test execution.
"""

import sys
from pathlib import Path

# Add the parent directory of TSC_CYCLE to sys.path
# This allows imports like "from TSC_CYCLE.benchmark.metrics import ..."
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
