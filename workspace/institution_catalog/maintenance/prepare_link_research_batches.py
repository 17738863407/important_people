"""把官网链接为空的机构均衡拆分为多个串行核查任务清单。"""

from __future__ import annotations

import logging
from pathlib import Path

from crawler_core.paths import resolve_project_path
from workspace.institution_catalog.maintenance.table_io import read_table, write_table


def configure_logging(log_path: Path) -> logging.Logger:
    """配置同时输出到控制台和 UTF-8 日志文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("prepare_link_research_batches")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="w")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def split_blank_official_rows(
    headers: list[str],
    rows: list[list[str]],
    batch_count: int,
) -> list[list[list[str]]]:
    """按正式表出现顺序筛出官网为空的记录，并均衡切成连续任务组。"""
    if batch_count <= 0:
        raise ValueError("任务组数量必须大于0")
    official_index = headers.index("官网链接")
    selected_rows = [row.copy() for row in rows if not row[official_index].strip()]
    quotient, remainder = divmod(len(selected_rows), batch_count)
    batches: list[list[list[str]]] = []
    start = 0
    for batch_index in range(batch_count):
        batch_size = quotient + (1 if batch_index < remainder else 0)
        batches.append(selected_rows[start : start + batch_size])
        start += batch_size
    return batches


def main(
    input_path: Path,
    output_dir: Path,
    log_path: Path,
    batch_count: int,
) -> None:
    """生成互不重叠的分组文件并验证总数和字段结构。"""
    logger = configure_logging(log_path)
    headers, rows = read_table(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    batches = split_blank_official_rows(headers, rows, batch_count)
    for batch_number, batch_rows in enumerate(batches, start=1):
        output_path = output_dir / f"第{batch_number}组-待查.txt"
        write_table(output_path, headers, batch_rows)
        verify_headers, verify_rows = read_table(output_path)
        if verify_headers != headers or verify_rows != batch_rows:
            raise ValueError(f"第{batch_number}组写出复核失败")
        logger.info("第%d组：%d条；文件=%s", batch_number, len(batch_rows), output_path)

    blank_count = sum(len(batch_rows) for batch_rows in batches)
    expected_blank_count = sum(
        1 for row in rows if not row[headers.index("官网链接")].strip()
    )
    if blank_count != expected_blank_count:
        raise ValueError(
            f"分组总数{blank_count}与官网空白总数{expected_blank_count}不一致"
        )
    logger.info("分组完成：%d组，共%d条", batch_count, blank_count)


if __name__ == "__main__":
    input_source_path = resolve_project_path(r"important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True)
    output_batch_dir = resolve_project_path(r"important_people/workspace/reports/机构目录/官网与领导链接待核查-分组", anchor=__file__)
    output_log_path = resolve_project_path(r"important_people/workspace/log/机构目录/链接核查任务分组.log", anchor=__file__)
    output_batch_count = 6
    main(input_source_path, output_batch_dir, output_log_path, output_batch_count)
