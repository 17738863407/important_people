from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tqdm import tqdm


OLD_HEADER = [
    "次序",
    "姓名*",
    "职务*",
    "排序*",
    "职级*",
    "所属省*",
    "所属市",
    "依据链接",
    "依据说明",
    "维护人",
    "机构",
    "详情页链接",
    "脚本序号",
]
NEW_HEADER = OLD_HEADER[1:]


@dataclass
class MigrationSummary:
    """记录迁移结果，便于最终核验和日志输出。"""

    total_files: int = 0
    migrated_files: int = 0
    skipped_files: int = 0
    migrated_rows: int = 0
    failures: int = 0


def write_log(log_path: Path, message: str) -> None:
    """同时向控制台和 UTF-8 日志写入运行信息。"""
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{message}"
    print(line)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def migrate_rows(path: Path) -> tuple[str, int]:
    """把旧十三列内容转换为新十二列内容，并返回新文本与数据行数。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError("文件为空")

    header = lines[0].split("\t")
    if header == NEW_HEADER:
        return "", 0
    if header != OLD_HEADER:
        raise ValueError(f"表头不符合旧十三列或新十二列契约：{header}")

    migrated_lines = ["\t".join(NEW_HEADER)]
    for line_number, line in enumerate(lines[1:], start=2):
        columns = line.split("\t")
        if len(columns) != len(OLD_HEADER):
            raise ValueError(f"第{line_number}行列数错误：应为13列，实际为{len(columns)}列")
        order_value = columns[0]
        migrated = columns[1:]
        migrated[NEW_HEADER.index("排序*")] = order_value
        migrated_lines.append("\t".join(migrated))
    return "\n".join(migrated_lines) + "\n", len(lines) - 1


def atomic_write_text(path: Path, content: str) -> None:
    """在原目录写入临时文件后原子替换，避免留下半写入结果。"""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def migrate_outputs(output_dir: Path, log_path: Path) -> MigrationSummary:
    """递归迁移输出目录中的全部 TXT，单文件失败时记录后继续。"""
    files = sorted(path for path in output_dir.rglob("*.txt") if path.is_file())
    summary = MigrationSummary(total_files=len(files))
    for path in tqdm(files, desc="迁移输出字段", unit="文件"):
        try:
            content, row_count = migrate_rows(path)
            if not content:
                summary.skipped_files += 1
                continue
            atomic_write_text(path, content)
            summary.migrated_files += 1
            summary.migrated_rows += row_count
        except Exception as error:
            summary.failures += 1
            write_log(log_path, f"迁移失败\t{path}\t{error}")
    write_log(
        log_path,
        "迁移汇总\t"
        f"TXT总数={summary.total_files}\t已迁移={summary.migrated_files}\t"
        f"已是新格式={summary.skipped_files}\t数据行={summary.migrated_rows}\t失败={summary.failures}",
    )
    return summary


def main(output_dir: Path, log_path: Path) -> None:
    """执行迁移，并在存在失败文件时返回错误。"""
    if not output_dir.is_dir():
        raise FileNotFoundError(f"输出目录不存在：{output_dir}")
    summary = migrate_outputs(output_dir, log_path)
    if summary.failures:
        raise RuntimeError(f"有{summary.failures}个TXT迁移失败，详见日志：{log_path}")


if __name__ == "__main__":
    project_root_value = Path(__file__).resolve().parents[2]
    output_dir_value = project_root_value / "outputs"
    log_path_value = project_root_value / "workspace" / "log" / "输出字段迁移.log"
    main(output_dir_value, log_path_value)
