from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil


PROJECT_NAME = "important_people"
PROJECT_MARKERS = ("AGENTS.md", "crawler_core", "workspace/source_data")
RUN_TIMESTAMP_PATTERN = re.compile(r"_\d{8}_\d{6}$")


def _anchor_directory(anchor: str | Path) -> Path:
    """把脚本文件或目录锚点规范为可向上查找的目录。"""
    path = Path(anchor).resolve()
    return path if path.is_dir() else path.parent


def find_project_root(anchor: str | Path) -> Path:
    """从脚本锚点向上按项目标记定位根目录，允许项目目录重命名。"""
    start = _anchor_directory(anchor)
    for candidate in (start, *start.parents):
        if all((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    raise FileNotFoundError(
        f"无法从锚点定位项目根目录：{anchor}；"
        f"要求包含 {', '.join(PROJECT_MARKERS)}"
    )


def resolve_project_path(
    value: str | Path,
    *,
    anchor: str | Path,
    must_exist: bool = False,
) -> Path:
    """以项目根目录解析相对路径，兼容旧 important_people/ 前缀。"""
    raw_value = str(value).strip().replace("\\", "/")
    windows_path = PureWindowsPath(raw_value)
    logical_path = PurePosixPath(raw_value)
    if not raw_value or windows_path.is_absolute() or windows_path.drive or logical_path.is_absolute():
        raise ValueError(f"只接受相对项目根目录的路径：{value}")
    if ".." in logical_path.parts:
        raise ValueError(f"路径不得包含 ..：{value}")

    relative_parts = logical_path.parts
    if relative_parts and relative_parts[0] == PROJECT_NAME:
        relative_parts = relative_parts[1:]

    project_root = find_project_root(anchor)
    resolved = project_root.joinpath(*relative_parts).resolve()
    if resolved != project_root and project_root not in resolved.parents:
        raise ValueError(f"路径越出项目根目录：{value}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"项目路径不存在：{value} -> {resolved}")
    return resolved


def resolve_path_argument(
    value: str | Path,
    *,
    anchor: str | Path,
    must_exist: bool = False,
) -> Path:
    """字符串相对项目根目录解析；Path 保留程序化调用的既有语义。"""
    if isinstance(value, Path):
        resolved = value.expanduser().resolve()
        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"路径不存在：{resolved}")
        return resolved
    return resolve_project_path(value, anchor=anchor, must_exist=must_exist)


def resolve_external_path(
    environment_name: str,
    *,
    must_exist: bool = True,
) -> Path:
    """从环境变量读取项目外部路径，避免在源码中绑定具体电脑目录。"""
    raw_value = os.environ.get(environment_name, "").strip()
    if not raw_value:
        raise RuntimeError(f"请通过环境变量 {environment_name} 配置项目外部路径")
    resolved = Path(raw_value).expanduser().resolve()
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"{environment_name} 指向的路径不存在：{resolved}")
    return resolved


def timestamped_output_path(
    path: str | Path,
    run_timestamp: str | None = None,
) -> Path:
    """为日志或报告文件名追加秒级运行时间，已有时间后缀时保持不变。"""
    output_path = Path(path)
    if RUN_TIMESTAMP_PATTERN.search(output_path.stem):
        return output_path
    timestamp = run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not re.fullmatch(r"\d{8}_\d{6}", timestamp):
        raise ValueError(f"运行时间格式应为 YYYYMMDD_HHMMSS：{timestamp}")
    return output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")


def find_chrome_executable() -> Path:
    """优先使用显式配置，其次按 Windows 环境变量和 PATH 查找 Chrome。"""
    configured = os.environ.get("IMPORTANT_PERSON_CHROME_EXE", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    for environment_name in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(environment_name, "").strip()
        if base:
            candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    command_path = shutil.which("chrome") or shutil.which("chrome.exe")
    if command_path:
        candidates.append(Path(command_path))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "未找到 Google Chrome；可通过 IMPORTANT_PERSON_CHROME_EXE 指定可执行文件"
    )


def find_powershell_executable() -> Path:
    """从显式配置、PATH 或 Program Files 中查找 PowerShell 7。"""
    configured = os.environ.get("IMPORTANT_PERSON_POWERSHELL_EXE", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    command_path = shutil.which("pwsh") or shutil.which("pwsh.exe")
    if command_path:
        candidates.append(Path(command_path))
    program_files = os.environ.get("PROGRAMFILES", "").strip()
    if program_files:
        candidates.append(Path(program_files) / "PowerShell" / "7" / "pwsh.exe")
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "未找到 PowerShell 7；可通过 IMPORTANT_PERSON_POWERSHELL_EXE 指定可执行文件"
    )
