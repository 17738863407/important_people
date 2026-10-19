from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台和日志文件。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def load_business_records(rule_table_path: Path) -> list[dict[str, object]]:
    """读取启用的业务记录，不读取任何页面技术画像。"""
    project_dir = rule_table_path.resolve().parents[2]
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.rule_table import load_generation_records

    return load_generation_records(rule_table_path)


def text_value(record: dict[str, object], key: str) -> str:
    """读取文本字段。"""
    value = record.get(key, "")
    return "" if value is None else str(value).strip()


def normalize_rule_id(value: str) -> str:
    """将 RULE_0001 等形式统一为四位脚本序号。"""
    match = re.search(r"(\d+)", str(value or ""))
    return match.group(1).zfill(4) if match else ""


def read_existing_rule_ids(adapter_dir: Path) -> set[str]:
    """递归读取已有脚本序号。"""
    rule_ids: set[str] = set()
    if not adapter_dir.exists():
        return rule_ids
    for script_path in adapter_dir.rglob("*.py"):
        match = re.match(r"(\d+)_", script_path.name)
        if match:
            rule_ids.add(match.group(1).zfill(4))
    return rule_ids


def exclusion_reason(record: dict[str, object]) -> str:
    """依据业务字段识别不进入脚本分析流程的记录。"""
    organization = text_value(record, "机构")
    url = text_value(record, "领导信息链接")
    note = text_value(record, "备注")
    combined = " ".join([organization, url, note])
    if not url:
        return "无依据链接"
    if "baike.baidu.com" in combined.lower() or "百度百科" in combined:
        return "百度百科"
    if note in {"空缺占位", "异常占位"}:
        return "占位"
    return ""


def write_manifest(output_path: Path, rows: list[list[str]]) -> None:
    """写入UTF-8制表符清单。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            cleaned = [str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in row]
            file.write("\t".join(cleaned) + "\n")


def main(
    rule_table_path: Path,
    adapter_dir: Path,
    success_dir: Path,
    output_manifest_path: Path,
    log_path: Path,
) -> None:
    """输出待逐页分析清单，不再依据主表中的历史画像批量生成脚本。"""
    if log_path.exists():
        log_path.unlink()
    records = load_business_records(rule_table_path)
    existing_rule_ids = read_existing_rule_ids(adapter_dir)
    _ = success_dir
    rows: list[list[str]] = [["脚本序号", "机构", "依据链接", "处理状态", "说明"]]
    excluded_count = 0
    existing_count = 0
    for record in records:
        rule_id = normalize_rule_id(text_value(record, "规则ID"))
        reason = exclusion_reason(record)
        if reason:
            excluded_count += 1
            continue
        if rule_id in existing_rule_ids:
            existing_count += 1
            continue
        rows.append([
            rule_id,
            text_value(record, "机构"),
            text_value(record, "领导信息链接"),
            "待逐页分析",
            "技术配置必须写入页面脚本，不再从规则主表推断",
        ])

    write_manifest(output_manifest_path, rows)
    write_log(log_path, "规则主表已缩减为业务字段，本工具不再自动复用历史技术画像。")
    write_log(log_path, f"业务记录数：{len(records)}")
    write_log(log_path, f"已有脚本记录数：{existing_count}")
    write_log(log_path, f"排除记录数：{excluded_count}")
    write_log(log_path, f"待逐页分析记录数：{len(rows) - 1}")
    write_log(log_path, f"分析清单：{output_manifest_path}")


if __name__ == "__main__":
    run_timestamp_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    rule_table_path_value = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    adapter_dir_value = resolve_project_path("important_people/site_adapters", anchor=__file__)
    success_dir_value = resolve_project_path(
        "important_people/site_adapters/脚本01：成功脚本", anchor=__file__
    )
    output_manifest_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/reports/待逐页分析脚本清单.txt", anchor=__file__
    ), run_timestamp_value)
    log_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/log/生成待逐页分析脚本清单.log", anchor=__file__
    ), run_timestamp_value)
    main(rule_table_path_value, adapter_dir_value, success_dir_value, output_manifest_path_value, log_path_value)
