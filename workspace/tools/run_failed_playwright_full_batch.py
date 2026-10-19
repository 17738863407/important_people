from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

try:
    from workspace.tools.project_paths import resolve_external_path, resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_external_path, resolve_project_path, timestamped_output_path


def load_batch_module(script_path: Path) -> ModuleType:
    """按文件路径加载批量运行器，兼容其中文文件名。"""
    spec = importlib.util.spec_from_file_location("important_people_batch_runner", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载批量运行器：{script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def collect_script_sequences(source_dir: Path, excluded_sequences: set[str]) -> tuple[str, ...]:
    """从用户提供的失败 TXT 文件名提取待运行脚本序号。"""
    sequences = {
        path.name[:4]
        for path in source_dir.glob("*.txt")
        if len(path.name) >= 5 and path.name[:4].isdigit()
    }
    return tuple(sorted(sequences - excluded_sequences))


def main(
    project_root: Path,
    source_dir: Path,
    output_dir: Path,
    log_path: Path,
    excluded_sequences: set[str],
) -> None:
    """运行失败目录对应的完整 Playwright 验证批次。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)
    runner = load_batch_module(project_root / "script2-爬取1-一键运行全部爬虫脚本.py")
    sequences = collect_script_sequences(source_dir, excluded_sequences)
    runner.main(
        adapter_dir=project_root / "site_adapters",
        script_sequence_filter=sequences,
        output_dir=output_dir,
        report_dir=project_root / "workspace" / "reports",
        log_path=log_path,
        python_exe=sys.executable,
        timeout_seconds=480,
        stop_on_error=False,
        execution_mode="in_process",
        max_workers=50,
        fetch_mode_chain=("raw_http", "requests", "playwright"),
        retry_worker_plan=({"raw_http": 30, "requests": 30, "playwright": 12},),
        delete_failed_output=False,
        fetch_mode_memory_path=project_root / "workspace" / "module" / "采集方式成功记录.txt",
        respect_fetch_mode_memory=True,
        respect_script_fetch_mode=False,
        update_fetch_mode_memory=True,
        same_domain_interval_seconds=1.5,
        same_domain_interval_by_mode={"raw_http": 1.5, "requests": 1.5, "playwright": 2.5},
        domain_backoff_seconds={"403": 15.0, "429": 30.0, "connection": 8.0},
        fetch_memory_flush_batch_size=50,
        hard_timeout_fetch_modes=(),
        collector_timeout_seconds_by_mode={"raw_http": 90, "requests": 90, "playwright": 150},
        success_folder_name="成功",
        failure_folder_name="失败",
    )


if __name__ == "__main__":
    project_root_value = resolve_project_path("important_people", anchor=__file__)
    source_dir_value = resolve_external_path("IMPORTANT_PERSON_FAILED_DIR")
    output_dir_value = project_root_value / "outputs" / "失败目录Playwright完整重跑_20261004"
    log_path_value = timestamped_output_path(
        project_root_value / "workspace" / "log" / "失败目录Playwright完整重跑.log"
    )
    excluded_sequences_value = {"0000", "1148"}
    main(project_root_value, source_dir_value, output_dir_value, log_path_value, excluded_sequences_value)
