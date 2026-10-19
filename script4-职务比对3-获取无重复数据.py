# -*- coding: utf-8 -*-
"""筛选官方更新提醒：本地职务与老数据职务没有任何完全相同元素的记录。

规则：
    1. 「本地职务」与「老数据职务」按中文逗号「，」、中文顿号「、」拆分为
       数据元素（老数据职务另按「/」拆分，因为多条老数据职务之间用「/」连接）。
    2. 只有元素完全相同时才算重复；「省委常委」与「四川省委常委」不算重复。
    3. 没有任何重复元素的记录才导出，整行保留原字段。
    4. 导出前按「提醒类型」排序：「需要新增」在前，「职务变更」在后，
       同类型内保持原始顺序。

输入固定为项目根目录下的「职务比对2：在线比对数据.txt」，输出固定为
「职务比对3：无重复数据.txt」。
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from crawler_core.paths import resolve_path_argument, timestamped_output_path


SPLIT_PATTERN = re.compile(r"[，、/]")
TYPE_ORDER = {"需要新增": 0, "职务变更": 1}


def setup_logging(log_path: Path) -> None:
    """配置日志：同时输出到控制台与日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def split_elements(text: str) -> list[str]:
    """把职务文本按中文逗号、中文顿号（老数据职务另含「/」）拆成元素。"""
    return [part.strip() for part in SPLIT_PATTERN.split(text) if part.strip()]


def has_overlap(local_duty: str, remote_duties: str) -> bool:
    """判断本地职务与老数据职务是否存在完全相同的元素。"""
    local_elems = set(split_elements(local_duty))
    remote_elems = set(split_elements(remote_duties))
    return bool(local_elems & remote_elems)


def read_rows(input_path: Path) -> tuple[str, list[list[str]]]:
    """读取 TSV：返回表头与各行单元格列表。"""
    rows: list[list[str]] = []
    with open(input_path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n")
        for line in fh:
            line = line.rstrip("\n")
            if line.strip():
                rows.append(line.split("\t"))
    return header, rows


def write_rows(output_path: Path, header: str, rows: list[list[str]]) -> None:
    """写出筛选后的 TSV。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for row in rows:
            fh.write("\t".join(row) + "\n")


def main(
    input_path: str | Path,
    output_path: str | Path,
    log_path: str | Path,
) -> None:
    """统一入口：读取在线比对文本，筛选无重复职务元素并排序导出。"""
    input_path = resolve_path_argument(input_path, anchor=__file__)
    output_path = resolve_path_argument(output_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    log_path = timestamped_output_path(log_path)
    setup_logging(log_path)
    if not input_path.is_file():
        logging.error("输入文件不存在：%s", input_path)
        raise SystemExit(1)
    logging.info("输入文件：%s", input_path)

    header, rows = read_rows(input_path)
    header_fields = header.split("\t")
    column_index = {name: index for index, name in enumerate(header_fields)}
    required_fields = ["姓名", "本地职务", "提醒类型", "老数据职务"]
    missing_fields = [name for name in required_fields if name not in column_index]
    if missing_fields:
        raise ValueError(f"输入文件缺少字段：{', '.join(missing_fields)}")

    name_index = column_index["姓名"]
    local_duty_index = column_index["本地职务"]
    reminder_type_index = column_index["提醒类型"]
    remote_duties_index = column_index["老数据职务"]
    logging.info("输入记录数：%d", len(rows))

    kept_rows: list[list[str]] = []
    excluded_rows: list[tuple[list[str], set[str]]] = []
    for row in rows:
        if len(row) < len(header_fields):
            logging.warning("跳过列数不足的行：%s", row)
            continue
        local_elems = set(split_elements(row[local_duty_index]))
        remote_elems = set(split_elements(row[remote_duties_index]))
        overlap = local_elems & remote_elems
        if overlap:
            excluded_rows.append((row, overlap))
        else:
            kept_rows.append(row)

    kept_rows.sort(key=lambda row: TYPE_ORDER.get(row[reminder_type_index], 99))
    write_rows(output_path, header, kept_rows)

    logging.info("筛选结果：保留 %d 行（无重复元素），排除 %d 行（存在重复元素）", len(kept_rows), len(excluded_rows))
    logging.info("输出文件：%s", output_path)

    type_counts: dict[str, int] = {}
    for row in kept_rows:
        reminder_type = row[reminder_type_index]
        type_counts[reminder_type] = type_counts.get(reminder_type, 0) + 1
    logging.info("保留行类型分布：%s", type_counts)

    if excluded_rows:
        logging.info("排除样例（前 5 条，显示重复元素）：")
        for row, overlap in excluded_rows[:5]:
            logging.info("  姓名=%s | 重复元素=%s", row[name_index], sorted(overlap))

    print(f"输出文件：{output_path}")
    print(f"保留 {len(kept_rows)} 行，排除 {len(excluded_rows)} 行")


if __name__ == "__main__":
    input_path_value = r"important_people/职务比对2：在线比对数据.txt"
    output_path_value = r"important_people/职务比对3：无重复数据.txt"
    log_path_value = r"important_people/workspace/log/职务比对/筛选无重复数据.log"
    main(input_path_value, output_path_value, log_path_value)
