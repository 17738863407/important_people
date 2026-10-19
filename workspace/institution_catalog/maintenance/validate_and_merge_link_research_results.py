"""独立复核六组链接核查结果并合并为根目录待核查表。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from tqdm import tqdm

from crawler_core.paths import resolve_project_path, timestamped_output_path
from workspace.institution_catalog.maintenance.table_io import (
    INSTITUTION_HEADERS,
    read_table,
    write_table,
)


def configure_logging(log_path: Path) -> logging.Logger:
    """配置同时输出到控制台和 UTF-8 日志文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("validate_and_merge_link_research_results")
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


def validate_url(value: str, location: str) -> None:
    """确认非空链接具有明确的 HTTP/HTTPS 协议和域名。"""
    if not value:
        return
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{location}不是有效HTTP/HTTPS链接：{value}")


def validate_group(
    batch_number: int,
    headers: list[str],
    input_rows: list[list[str]],
    result_rows: list[list[str]],
) -> dict[str, int]:
    """核对单组行数、非目标字段和所有新增链接。"""
    if len(input_rows) != len(result_rows):
        raise ValueError(
            f"第{batch_number}组结果行数{len(result_rows)}与待查行数{len(input_rows)}不一致"
        )
    official_index = headers.index("官网链接")
    leader_index = headers.index("领导链接")
    protected_indexes = [
        index for index in range(len(headers)) if index not in {official_index, leader_index}
    ]
    official_count = 0
    leader_count = 0
    both_count = 0

    for row_number, (input_row, result_row) in enumerate(
        tqdm(
            zip(input_rows, result_rows, strict=True),
            total=len(input_rows),
            desc=f"复核第{batch_number}组",
            unit="条",
        ),
        start=2,
    ):
        for index in protected_indexes:
            if input_row[index] != result_row[index]:
                raise ValueError(
                    f"第{batch_number}组第{row_number}行非目标字段“{headers[index]}”发生变化"
                )
        official_url = result_row[official_index].strip()
        leader_url = result_row[leader_index].strip()
        validate_url(official_url, f"第{batch_number}组第{row_number}行官网链接")
        validate_url(leader_url, f"第{batch_number}组第{row_number}行领导链接")
        official_count += bool(official_url)
        leader_count += bool(leader_url)
        both_count += bool(official_url and leader_url)
    return {
        "rows": len(result_rows),
        "official": official_count,
        "leader": leader_count,
        "both": both_count,
    }


def main(
    source_path: Path,
    batch_dir: Path,
    output_path: Path,
    log_path: Path,
    batch_count: int,
) -> None:
    """复核来源覆盖关系、六组结果结构并生成最终合并文件。"""
    logger = configure_logging(log_path)
    expected_headers = INSTITUTION_HEADERS
    source_headers, source_rows = read_table(source_path)
    if source_headers != expected_headers:
        raise ValueError(f"机构全量表字段或顺序异常：{source_headers}")

    official_index = source_headers.index("官网链接")
    expected_input_rows = [
        row.copy() for row in source_rows if not row[official_index].strip()
    ]
    combined_input_rows: list[list[str]] = []
    combined_result_rows: list[list[str]] = []
    totals = {"rows": 0, "official": 0, "leader": 0, "both": 0}

    for batch_number in range(1, batch_count + 1):
        input_path = batch_dir / f"第{batch_number}组-待查.txt"
        result_path = batch_dir / f"第{batch_number}组-结果.txt"
        input_headers, input_rows = read_table(input_path)
        result_headers, result_rows = read_table(result_path)
        if input_headers != expected_headers or result_headers != expected_headers:
            raise ValueError(f"第{batch_number}组字段或字段顺序异常")
        stats = validate_group(
            batch_number,
            expected_headers,
            input_rows,
            result_rows,
        )
        combined_input_rows.extend(input_rows)
        combined_result_rows.extend(result_rows)
        for key in totals:
            totals[key] += stats[key]
        logger.info(
            "第%d组：%d条；官网%d；领导页%d；双链接%d",
            batch_number,
            stats["rows"],
            stats["official"],
            stats["leader"],
            stats["both"],
        )

    if combined_input_rows != expected_input_rows:
        raise ValueError("六组待查记录未按原表顺序完整覆盖全部官网空白记录")

    write_table(output_path, expected_headers, combined_result_rows)
    verify_headers, verify_rows = read_table(output_path)
    if verify_headers != expected_headers or verify_rows != combined_result_rows:
        raise ValueError("最终合并文件写出复核失败")
    logger.info("合并完成：%d条", totals["rows"])
    logger.info("官网已找到：%d条", totals["official"])
    logger.info("领导链接已找到：%d条", totals["leader"])
    logger.info("两者均找到：%d条", totals["both"])
    logger.info("最终文件：%s", output_path)


if __name__ == "__main__":
    input_source_path = resolve_project_path(r"important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True)
    input_batch_dir = resolve_project_path(r"important_people/workspace/reports/机构目录/官网与领导链接待核查-分组", anchor=__file__)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_result_path = timestamped_output_path(
        resolve_project_path(
            r"important_people/workspace/reports/机构目录/官网与领导链接待核查.txt",
            anchor=__file__,
        ),
        run_timestamp,
    )
    output_log_path = timestamped_output_path(
        resolve_project_path(
            r"important_people/workspace/log/机构目录/链接核查结果合并复核.log",
            anchor=__file__,
        ),
        run_timestamp,
    )
    input_batch_count = 6
    main(
        input_source_path,
        input_batch_dir,
        output_result_path,
        output_log_path,
        input_batch_count,
    )
