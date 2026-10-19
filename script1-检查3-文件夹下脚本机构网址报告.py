from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from crawler_core.paths import resolve_path_argument


def print_and_log(message: str, log_lines: list[str]) -> None:
    """同时向控制台和日志缓存输出信息。"""
    print(message)
    log_lines.append(message)


def normalize_rule_number(rule_id: str) -> str:
    """从 RULE_1907 或 1907 等形式中提取四位序号。"""
    match = re.search(r"(\d+)", rule_id)
    if not match:
        return ""
    return match.group(1).zfill(4)


def load_source_mapping(rule_table_path: Path) -> dict[str, dict[str, str]]:
    """读取V3唯一权威规则主表，建立“四位序号 -> 机构与依据链接”的映射。"""
    from crawler_core.rule_table import load_rule_table

    source_mapping: dict[str, dict[str, str]] = {}
    for record in load_rule_table(rule_table_path):
        rule_number = normalize_rule_number(record.get("脚本序号", ""))
        if not rule_number:
            continue
        source_mapping[rule_number] = {
            "rule_id": rule_number,
            "organization": str(record.get("机构名称", "")).strip(),
            "url": str(record.get("领导链接", "")).strip(),
        }
    return source_mapping


def collect_script_records(scripts_dir: Path, source_mapping: dict[str, dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """递归扫描V3脚本，只使用文件名前缀序号匹配权威业务源。"""
    records: list[dict[str, str]] = []
    skipped_non_rule_count = 0
    script_files = sorted(scripts_dir.rglob("*.py"), key=lambda item: str(item.relative_to(scripts_dir)).lower())

    for script_path in script_files:
        match = re.match(r"^(\d+)_", script_path.name)
        if not match:
            skipped_non_rule_count += 1
            continue

        rule_number = match.group(1).zfill(4)
        source_record = source_mapping.get(rule_number)
        if source_record is None:
            records.append(
                {
                    "序号": rule_number,
                    "规则ID": f"RULE_{rule_number}",
                    "脚本文件名": str(script_path.relative_to(scripts_dir)),
                    "机构": "",
                    "网址": "",
                    "匹配状态": "源数据未匹配",
                }
            )
            continue

        records.append(
            {
                "序号": rule_number,
                "规则ID": source_record["rule_id"],
                "脚本文件名": str(script_path.relative_to(scripts_dir)),
                "机构": source_record["organization"],
                "网址": source_record["url"],
                "匹配状态": "已匹配",
            }
        )

    return records, skipped_non_rule_count


def write_txt_report(records: list[dict[str, str]], output_path: Path) -> None:
    """按制表符分隔格式写出 txt 报告。"""
    columns = ["机构", "网址"]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        file.write("\t".join(columns) + "\n")
        for record in records:
            row = [record.get(column, "") for column in columns]
            file.write("\t".join(row) + "\n")


def write_log(log_lines: list[str], log_path: Path) -> None:
    """将运行日志写入 UTF-8 文本文件。"""
    with log_path.open("w", encoding="utf-8", newline="") as file:
        file.write("\n".join(log_lines) + "\n")


def main(
    project_root: str | Path,
    scripts_dir: str | Path,
    rule_table_path: str | Path,
    output_prefix: str,
) -> Path:
    """生成脚本序号对应机构与网址的 txt 报告。"""
    project_root = resolve_path_argument(project_root, anchor=__file__, must_exist=True)
    scripts_dir = resolve_path_argument(scripts_dir, anchor=__file__, must_exist=True)
    rule_table_path = resolve_path_argument(
        rule_table_path, anchor=__file__, must_exist=True
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = project_root / f"{output_prefix}_{timestamp}.txt"
    log_dir = project_root / "workspace" / "log"
    log_path = log_dir / f"{output_prefix}_{timestamp}.log.txt"
    log_lines: list[str] = []

    print_and_log(f"项目根目录：{project_root}", log_lines)
    print_and_log(f"脚本目录：{scripts_dir}", log_lines)
    print_and_log(f"权威规则主表：{rule_table_path}", log_lines)

    if not scripts_dir.exists():
        raise FileNotFoundError(f"脚本目录不存在：{scripts_dir}")
    if not rule_table_path.is_file():
        raise FileNotFoundError(f"权威规则主表不存在：{rule_table_path}")

    source_mapping = load_source_mapping(rule_table_path)
    print_and_log(f"源数据有效规则数：{len(source_mapping)}", log_lines)

    records, skipped_non_rule_count = collect_script_records(scripts_dir, source_mapping)
    matched_count = sum(1 for record in records if record["匹配状态"] == "已匹配")
    unmatched_count = len(records) - matched_count

    write_txt_report(records, output_path)
    log_dir.mkdir(parents=True, exist_ok=True)

    print_and_log(f"纳入报告脚本数：{len(records)}", log_lines)
    print_and_log(f"跳过非规则序号脚本数：{skipped_non_rule_count}", log_lines)
    print_and_log(f"已匹配数：{matched_count}", log_lines)
    print_and_log(f"未匹配数：{unmatched_count}", log_lines)
    print_and_log(f"报告路径：{output_path}", log_lines)
    print_and_log(f"日志路径：{log_path}", log_lines)
    write_log(log_lines, log_path)

    return output_path


if __name__ == "__main__":
    project_root_param = r"important_people"
    scripts_dir_param = r"important_people/site_adapters/V3"
    rule_table_path_param = r"important_people/workspace/source_data/规则主表.txt"
    output_prefix_param = "机构网址报告"
    main(project_root_param, scripts_dir_param, rule_table_path_param, output_prefix_param)
