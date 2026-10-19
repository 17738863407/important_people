from __future__ import annotations

from pathlib import Path

from crawler_core.models import PersonRecord


OUTPUT_FIELDS = [
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


def safe_tsv_cell(value: object) -> str:
    """清理制表符和换行，避免破坏 TXT 表格结构。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def record_to_output_row(row: PersonRecord, fallback_order: int | str = "") -> dict[str, str]:
    """将兼容记录映射为统一 TXT 字段，并把页面次序写入“排序*”。"""
    return {
        "姓名*": row.name,
        "职务*": "",
        "排序*": row.order or str(fallback_order),
        "职级*": "",
        "所属省*": row.province,
        "所属市": row.city,
        "依据链接": row.url,
        "依据说明": row.evidence,
        "维护人": "",
        "机构": row.organization,
        "详情页链接": row.detail_url,
        "脚本序号": row.script_sequence,
    }


def export_records(path: Path, rows: list[PersonRecord]) -> None:
    """导出新方案在线采集结果。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write("\t".join(OUTPUT_FIELDS) + "\n")
        for index, row in enumerate(rows, start=1):
            output_row = record_to_output_row(row, fallback_order=index)
            file.write("\t".join(safe_tsv_cell(output_row.get(field, "")) for field in OUTPUT_FIELDS) + "\n")
