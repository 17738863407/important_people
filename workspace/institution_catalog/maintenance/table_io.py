"""机构主表维护脚本共用的十二字段读写契约。"""

from __future__ import annotations

from pathlib import Path


INSTITUTION_HEADERS = [
    "组织体系",
    "目录链接",
    "机构类型",
    "机构层级",
    "所属省*",
    "所属市",
    "机构名称",
    "机构别称",
    "官网链接",
    "领导链接",
    "脚本序号",
    "备注",
]


def read_table(input_path: Path) -> tuple[list[str], list[list[str]]]:
    """读取 UTF-8 TSV，并严格执行机构主表十二字段契约。"""
    lines = input_path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{input_path}")
    headers = lines[0].split("\t")
    if headers != INSTITUTION_HEADERS:
        raise ValueError(f"机构主表字段或顺序异常：{headers}")

    rows: list[list[str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        values = line.split("\t")
        if len(values) != len(headers):
            raise ValueError(
                f"{input_path.name}第{line_number}行字段数为{len(values)}，"
                f"应为{len(headers)}"
            )
        rows.append(values)
    return headers, rows


def write_table(output_path: Path, headers: list[str], rows: list[list[str]]) -> None:
    """用 UTF-8、制表符和 CRLF 写出十二字段表。"""
    if headers != INSTITUTION_HEADERS:
        raise ValueError(f"拒绝写出非十二字段机构表：{headers}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(headers), *("\t".join(row) for row in rows)]
    output_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
