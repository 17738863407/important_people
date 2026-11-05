# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pypinyin>=0.51.0",
# ]
# ///

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Sequence

from pypinyin import Style, lazy_pinyin


def normalize_header(value: str) -> str:
    """去掉 BOM、空白和列名中的星号，便于精确匹配列名。"""
    return value.strip().lstrip("\ufeff").replace("*", "").strip()


def pinyin_key(value: str) -> tuple[str, ...]:
    """将中文文本转换为拼音序列，用于稳定排序。"""
    text = (value or "").strip()
    if not text:
        return ("",)
    return tuple(lazy_pinyin(text, style=Style.NORMAL))


def find_column(headers: Sequence[str], aliases: Iterable[str], label: str) -> int:
    """按候选列名查找列索引；先精确匹配归一化后的列名，再兜底包含匹配。"""
    normalized_headers = [normalize_header(header) for header in headers]
    normalized_aliases = [normalize_header(alias) for alias in aliases]

    for alias in normalized_aliases:
        if alias in normalized_headers:
            return normalized_headers.index(alias)

    for alias in normalized_aliases:
        if not alias:
            continue
        for index, header in enumerate(normalized_headers):
            if alias in header:
                return index

    raise KeyError(
        f"找不到{label}列；候选列名={list(aliases)}；实际表头={list(headers)}"
    )


def setup_logging() -> logging.Logger:
    """仅向控制台输出运行信息，不写日志文件。"""
    logger = logging.getLogger("sort_important_people")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def detect_bom(path: str) -> bool:
    """检测原文件是否带 UTF-8 BOM，写回时保持一致。"""
    with open(path, "rb") as file:
        return file.read(3) == b"\xef\xbb\xbf"


def read_table(input_path: str, logger: logging.Logger) -> tuple[list[str], list[str]]:
    """读取 UTF-8、制表符分隔、首行表头的文本表格。"""
    with open(input_path, "r", encoding="utf-8-sig", newline="") as file:
        lines = file.read().splitlines()

    if not lines:
        raise ValueError(f"输入文件为空：{input_path}")

    header_line = lines[0]
    if "\t" not in header_line:
        raise ValueError(
            "首行表头未检测到制表符。请确认输入为 UTF-8、制表符分隔、首行表头的 .txt 表格。"
        )

    headers = header_line.split("\t")
    data_lines = lines[1:]

    logger.info("读取文件：%s", input_path)
    logger.info("表头列数：%d；数据行数：%d", len(headers), len(data_lines))
    return headers, data_lines


def build_sort_key(
    row: Sequence[str],
    indexes: dict[str, int],
    org_rank: dict[str, int],
    org_order_length: int,
) -> tuple[Any, ...]:
    """构造排序键：组织体系顺序、机构类型拼音、机构层级拼音、省、市、名称。"""

    def cell(field: str) -> str:
        return row[indexes[field]].strip()

    organization = cell("org")
    organization_key = (
        org_rank.get(organization, org_order_length),
        pinyin_key(organization),
    )

    return (
        organization_key,
        pinyin_key(cell("org_type")),
        pinyin_key(cell("org_level")),
        pinyin_key(cell("province")),
        pinyin_key(cell("city")),
        pinyin_key(cell("name")),
    )


def sort_rows(
    data_lines: Sequence[str],
    headers: Sequence[str],
    column_aliases: dict[str, Sequence[str]],
    org_order: Sequence[str],
    logger: logging.Logger,
) -> tuple[list[str], list[str]]:
    """按业务规则排序；列数异常的行保留到输出末尾。"""
    indexes = {
        "org": find_column(headers, column_aliases["org"], "组织体系"),
        "org_type": find_column(headers, column_aliases["org_type"], "机构类型"),
        "org_level": find_column(headers, column_aliases["org_level"], "机构层级"),
        "province": find_column(headers, column_aliases["province"], "所属省*"),
        "city": find_column(headers, column_aliases["city"], "所属市"),
        "name": find_column(headers, column_aliases["name"], "机构名称"),
    }

    org_rank = {item.strip(): index for index, item in enumerate(org_order)}

    valid_lines: list[str] = []
    invalid_lines: list[str] = []

    for line_number, raw_line in enumerate(data_lines, start=2):
        if raw_line.strip() == "":
            logger.warning("第 %d 行为空行，已跳过。", line_number)
            continue

        row = raw_line.split("\t")
        if len(row) != len(headers):
            logger.warning(
                "第 %d 行列数为 %d，与表头列数 %d 不一致，已原样追加到输出末尾。",
                line_number,
                len(row),
                len(headers),
            )
            invalid_lines.append(raw_line)
            continue

        valid_lines.append(raw_line)

    def sort_key(raw_line: str) -> tuple[Any, ...]:
        row = raw_line.split("\t")
        return build_sort_key(row, indexes, org_rank, len(org_order))

    sorted_lines = sorted(valid_lines, key=sort_key)
    logger.info("有效数据行：%d；异常行：%d", len(sorted_lines), len(invalid_lines))
    return sorted_lines, invalid_lines


def write_table_in_place(
    target_path: str,
    headers: Sequence[str],
    sorted_lines: Sequence[str],
    invalid_lines: Sequence[str],
    use_bom: bool,
    logger: logging.Logger,
) -> None:
    """先写同目录临时文件，再原子替换原文件，避免中途失败损坏原文件。"""
    encoding = "utf-8-sig" if use_bom else "utf-8"
    tmp_path = target_path + ".tmp"

    with open(tmp_path, "w", encoding=encoding, newline="") as file:
        file.write("\t".join(headers) + "\n")
        for line in sorted_lines:
            file.write(line + "\n")
        for line in invalid_lines:
            file.write(line + "\n")

    os.replace(tmp_path, target_path)
    logger.info("已原地写回：%s", target_path)
    logger.info("输出总行数：%d（含表头）", 1 + len(sorted_lines) + len(invalid_lines))


def main(
    input_path: str,
    org_order: Sequence[str],
    column_aliases: dict[str, Sequence[str]],
) -> None:
    """统一入口：读取、排序并原地写回同一文件。"""
    logger = setup_logging()

    try:
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"找不到输入文件：{input_path}")

        logger.info("开始按组织体系/机构类型/机构层级/所属省*/所属市/机构名称排序。")
        use_bom = detect_bom(input_path)
        headers, data_lines = read_table(input_path, logger)
        sorted_lines, invalid_lines = sort_rows(
            data_lines,
            headers,
            column_aliases,
            org_order,
            logger,
        )
        write_table_in_place(
            input_path,
            headers,
            sorted_lines,
            invalid_lines,
            use_bom,
            logger,
        )
        logger.info("完成。")
    except Exception:
        logger.exception("处理失败")
        raise


if __name__ == "__main__":
    input_path = r"C:\Users\wikipedia\Desktop\important_people\workspace\source_data\规则主表.txt"
    org_order = [
        "中共中央",
        "全国人大",
        "国务院",
        "全国政协",
        "最高人民法院",
        "最高人民检察院",
        "法院",
        "检察院",
        "纪委监委",
        "民主党派",
        "群团组织",
        "省级四大",
        "省厅领导",
        "地级四大",
        "市局领导",
        "央企",
        "其他",
    ]
    column_aliases = {
        "org": ("组织体系",),
        "org_type": ("机构类型",),
        "org_level": ("机构层级",),
        "province": ("所属省*",),
        "city": ("所属市",),
        "name": ("机构名称",),
    }
    main(input_path, org_order, column_aliases)