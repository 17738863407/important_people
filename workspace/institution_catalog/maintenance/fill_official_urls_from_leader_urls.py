"""依据领导人物介绍页的站点域名补充机构官网链接。"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from tqdm import tqdm

from crawler_core.paths import resolve_project_path, timestamped_output_path
from workspace.institution_catalog.maintenance.table_io import read_table


def configure_logging(log_path: Path) -> logging.Logger:
    """配置同时输出到控制台和 UTF-8 日志文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fill_official_urls_from_leader_urls")
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


def official_url_from_leader_url(leader_url: str) -> str:
    """从有效的 HTTP/HTTPS 领导链接生成同协议、同域名的站点根地址。"""
    parsed = urlsplit(leader_url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"领导链接不是有效的 HTTP/HTTPS 地址：{leader_url}")
    return f"{parsed.scheme.lower()}://{parsed.netloc}/"


def fill_official_urls(
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[list[str]], int, int]:
    """只为官网链接为空且领导链接有效的记录补值。"""
    official_index = headers.index("官网链接")
    leader_index = headers.index("领导链接")
    updated_rows = [row.copy() for row in rows]
    filled_count = 0
    skipped_count = 0

    for row in tqdm(updated_rows, desc="补充官网链接", unit="条"):
        if row[official_index].strip():
            continue
        leader_url = row[leader_index].strip()
        if not leader_url:
            skipped_count += 1
            continue
        row[official_index] = official_url_from_leader_url(leader_url)
        filled_count += 1
    return updated_rows, filled_count, skipped_count


def write_table_atomic(
    output_path: Path,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    """使用 UTF-8、制表符和 CRLF 写入临时文件，复核后原子替换正式表。"""
    temporary_path = output_path.with_name(f"{output_path.name}.official-url.tmp")
    if temporary_path.exists():
        raise FileExistsError(f"存在未处理的临时文件：{temporary_path}")
    lines = ["\t".join(headers), *("\t".join(row) for row in rows)]
    temporary_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
    verify_headers, verify_rows = read_table(temporary_path)
    if verify_headers != headers or verify_rows != rows:
        raise ValueError("临时文件复核失败")
    os.replace(temporary_path, output_path)


def main(
    input_path: Path,
    backup_dir: Path,
    log_path: Path,
) -> None:
    """备份正式表，补充官网链接并完成写回校验。"""
    logger = configure_logging(log_path)
    headers, rows = read_table(input_path)
    updated_rows, filled_count, skipped_count = fill_official_urls(headers, rows)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"机构主表-补充官网链接前-{timestamp}.txt"
    shutil.copy2(input_path, backup_path)
    write_table_atomic(input_path, headers, updated_rows)

    final_headers, final_rows = read_table(input_path)
    if final_headers != headers or len(final_rows) != len(rows):
        raise ValueError("正式表写回后结构或记录数发生变化")
    logger.info("正式表记录数：%d", len(final_rows))
    logger.info("新增官网链接：%d", filled_count)
    logger.info("因缺少领导链接而保留为空：%d", skipped_count)
    logger.info("备份文件：%s", backup_path)


if __name__ == "__main__":
    input_source_path = resolve_project_path(r"important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True)
    output_backup_dir = resolve_project_path(r"important_people/workspace/source_data/backup/机构主表", anchor=__file__)
    output_log_path = timestamped_output_path(
        resolve_project_path(
            r"important_people/workspace/log/机构目录/官网链接补充.log",
            anchor=__file__,
        )
    )
    main(input_source_path, output_backup_dir, output_log_path)
