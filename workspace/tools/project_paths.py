from __future__ import annotations

import sys
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from crawler_core.paths import (  # noqa: E402
    find_chrome_executable,
    find_powershell_executable,
    find_project_root,
    resolve_external_path,
    resolve_project_path,
    timestamped_output_path,
)

__all__ = [
    "find_chrome_executable",
    "find_powershell_executable",
    "find_project_root",
    "resolve_external_path",
    "resolve_project_path",
    "timestamped_output_path",
]
