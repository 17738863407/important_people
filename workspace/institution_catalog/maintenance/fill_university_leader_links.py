"""将高校领导页面核验结果写入机构全量表的领导链接列。"""

from __future__ import annotations

import csv
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from tqdm import tqdm

from crawler_core.paths import resolve_project_path, timestamped_output_path
from workspace.institution_catalog.maintenance.table_io import INSTITUTION_HEADERS


def build_logger(log_path: Path) -> logging.Logger:
    """创建同时输出到控制台和 UTF-8 日志文件的记录器。"""
    logger = logging.getLogger("fill_university_leader_links")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def normalize_name(value: str) -> str:
    """去除名称中的全部空白，用于兼容括号前多余空格。"""
    return re.sub(r"\s+", "", value)


def extract_host(url: str) -> str:
    """提取并规范化网址主机名。"""
    return (urlparse(url.strip()).hostname or "").lower()


def split_line_ending(line: str) -> tuple[str, str]:
    """拆分正文与原始换行符，以便保留文件的混合换行格式。"""
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return line[: -len(ending)], ending
    return line, ""


def load_source_rows(source_path: Path) -> list[dict[str, str]]:
    """读取并校验高校领导链接来源表。"""
    with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file, delimiter="\t")
        required_headers = {"机构名称", "输入官网", "最终官网", "领导链接"}
        if reader.fieldnames is None or not required_headers.issubset(reader.fieldnames):
            raise ValueError(f"来源表字段不符合预期：{reader.fieldnames}")
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("来源表没有可处理记录")

    normalized_names = [normalize_name(row["机构名称"]) for row in rows]
    if len(normalized_names) != len(set(normalized_names)):
        raise ValueError("来源表存在规范化后重复的机构名称")

    for row_number, row in enumerate(rows, start=2):
        if not row["机构名称"].strip():
            raise ValueError(f"来源表第 {row_number} 行机构名称为空")
        if not extract_host(row["领导链接"]):
            raise ValueError(f"来源表第 {row_number} 行领导链接无效：{row['领导链接']}")
    return rows


def parse_main_lines(
    lines: list[str], expected_headers: list[str]
) -> tuple[list[str], list[list[str]], list[str]]:
    """解析主表，并分别保留每一行原有的换行符。"""
    if not lines:
        raise ValueError("机构全量表为空")
    header_text, header_ending = split_line_ending(lines[0])
    headers = header_text.split("\t")
    if headers != expected_headers:
        raise ValueError(f"机构全量表字段或顺序异常：{headers}")

    rows: list[list[str]] = []
    endings: list[str] = [header_ending]
    for row_number, line in enumerate(lines[1:], start=2):
        row_text, ending = split_line_ending(line)
        fields = row_text.split("\t")
        if len(fields) != len(headers):
            raise ValueError(
                f"机构全量表第 {row_number} 行字段数异常：{len(fields)}"
            )
        rows.append(fields)
        endings.append(ending)
    return headers, rows, endings


def update_rows(
    headers: list[str],
    main_rows: list[list[str]],
    source_rows: list[dict[str, str]],
) -> tuple[list[list[str]], list[tuple[str, str, str]]]:
    """唯一匹配高校记录，并仅替换领导链接字段。"""
    name_index = headers.index("机构名称")
    official_index = headers.index("官网链接")
    leader_index = headers.index("领导链接")

    index_by_name: dict[str, list[int]] = {}
    for row_index, row in enumerate(main_rows):
        index_by_name.setdefault(normalize_name(row[name_index]), []).append(row_index)

    updated_rows = [row.copy() for row in main_rows]
    changes: list[tuple[str, str, str]] = []
    for source_row in tqdm(source_rows, desc="填写高校领导链接", unit="条"):
        institution_name = source_row["机构名称"].strip()
        matched_indexes = index_by_name.get(normalize_name(institution_name), [])
        if len(matched_indexes) != 1:
            raise ValueError(
                f"机构名称未能唯一匹配：{institution_name}；匹配数={len(matched_indexes)}"
            )

        row_index = matched_indexes[0]
        main_host = extract_host(updated_rows[row_index][official_index])
        accepted_hosts = {
            extract_host(source_row["输入官网"]),
            extract_host(source_row["最终官网"]),
        }
        accepted_hosts.discard("")
        if main_host not in accepted_hosts:
            raise ValueError(
                f"官网域名不一致：{institution_name}；主表={main_host}；"
                f"来源={sorted(accepted_hosts)}"
            )

        old_url = updated_rows[row_index][leader_index]
        new_url = source_row["领导链接"].strip()
        updated_rows[row_index][leader_index] = new_url
        changes.append((institution_name, old_url, new_url))
    return updated_rows, changes


def validate_only_leader_column_changed(
    headers: list[str], original_rows: list[list[str]], updated_rows: list[list[str]]
) -> None:
    """确认记录数、顺序及所有非领导链接字段完全不变。"""
    if len(original_rows) != len(updated_rows):
        raise ValueError("写入前后记录数发生变化")
    leader_index = headers.index("领导链接")
    for row_number, (before, after) in enumerate(
        zip(original_rows, updated_rows, strict=True), start=2
    ):
        for column_index, (old_value, new_value) in enumerate(
            zip(before, after, strict=True)
        ):
            if column_index != leader_index and old_value != new_value:
                raise ValueError(
                    f"第 {row_number} 行非目标字段被修改：{headers[column_index]}"
                )


def write_atomic(
    table_path: Path,
    headers: list[str],
    rows: list[list[str]],
    endings: list[str],
) -> None:
    """在同目录生成候选文件，复读后原子替换正式表。"""
    temporary_path = table_path.with_name(f".{table_path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as output_file:
        output_file.write("\t".join(headers) + endings[0])
        for row_index, row in enumerate(rows, start=1):
            output_file.write("\t".join(row) + endings[row_index])

    with temporary_path.open("r", encoding="utf-8", newline="") as check_file:
        check_lines = check_file.readlines()
    check_headers, check_rows, _ = parse_main_lines(check_lines, headers)
    if check_headers != headers or check_rows != rows:
        raise ValueError("候选文件复读校验失败")
    os.replace(temporary_path, table_path)


def main(
    source_path: Path,
    table_path: Path,
    backup_dir: Path,
    log_path: Path,
) -> None:
    """完成读取、唯一匹配、备份、写入和复核。"""
    logger = build_logger(log_path)
    expected_headers = INSTITUTION_HEADERS

    source_rows = load_source_rows(source_path)
    with table_path.open("r", encoding="utf-8", newline="") as table_file:
        original_lines = table_file.readlines()
    headers, original_rows, endings = parse_main_lines(original_lines, expected_headers)
    updated_rows, changes = update_rows(headers, original_rows, source_rows)
    validate_only_leader_column_changed(headers, original_rows, updated_rows)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"机构主表-高校领导链接填写前-{timestamp}.txt"
    shutil.copy2(table_path, backup_path)
    write_atomic(table_path, headers, updated_rows, endings)

    with table_path.open("r", encoding="utf-8", newline="") as table_file:
        final_lines = table_file.readlines()
    final_headers, final_rows, _ = parse_main_lines(final_lines, expected_headers)
    validate_only_leader_column_changed(final_headers, original_rows, final_rows)

    changed_count = sum(old_url != new_url for _, old_url, new_url in changes)
    logger.info("来源记录数：%d", len(source_rows))
    logger.info("机构主表记录数：%d", len(final_rows))
    logger.info("成功匹配并填写：%d", len(changes))
    logger.info("实际发生变化：%d", changed_count)
    logger.info("备份文件：%s", backup_path)
    logger.info("正式文件：%s", table_path)
    for institution_name, old_url, new_url in changes:
        logger.info("更新：%s\t%s\t%s", institution_name, old_url, new_url)


if __name__ == "__main__":
    input_source_path = resolve_project_path(r"important_people/workspace/reports/机构目录/高校领导链接核验结果.txt", anchor=__file__, must_exist=True)
    input_table_path = resolve_project_path(r"important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True)
    output_backup_dir = resolve_project_path(r"important_people/workspace/source_data/backup/机构主表", anchor=__file__)
    output_log_path = timestamped_output_path(
        resolve_project_path(
            r"important_people/workspace/log/机构目录/高校领导链接填写.log",
            anchor=__file__,
        )
    )
    main(input_source_path, input_table_path, output_backup_dir, output_log_path)
