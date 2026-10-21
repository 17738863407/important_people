"""按规则主表同步页面脚本、抽取结果文件名及结果内机构字段。"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crawler_core.naming import build_output_name, build_script_name, script_sequence_from_filename
from crawler_core.paths import resolve_project_path
from crawler_core.rule_table import load_rule_table


OUTPUT_INSTITUTION_HEADER = "机构"


@dataclass(frozen=True)
class AuditItem:
    """记录一项比对、改名或字段同步结果。"""

    category: str
    sequence: str
    path: Path
    status: str
    detail: str


def collect_artifacts(directory: Path, suffix: str) -> dict[str, list[Path]]:
    """按文件名四位序号收集指定扩展名的全部产物。"""
    artifacts: dict[str, list[Path]] = defaultdict(list)
    for path in directory.rglob(f"*{suffix}"):
        if not path.is_file():
            continue
        sequence = script_sequence_from_filename(path.name)
        if sequence:
            artifacts[sequence].append(path)
    return artifacts


def read_output_rows(path: Path) -> tuple[list[str], list[list[str]], str]:
    """读取 UTF-8 TSV，并保留其原始换行风格。"""
    raw_text = path.read_text(encoding="utf-8-sig")
    line_ending = "\r\n" if "\r\n" in raw_text else "\n"
    lines = raw_text.splitlines()
    if not lines:
        raise ValueError("文件为空")
    header = lines[0].split("\t")
    rows: list[list[str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        values = line.split("\t")
        if len(values) != len(header):
            raise ValueError(f"第 {line_number} 行列数为 {len(values)}，表头列数为 {len(header)}")
        rows.append(values)
    return header, rows, line_ending


def synchronize_output_institution(
    path: Path,
    institution: str,
    dry_run: bool,
) -> tuple[bool, str]:
    """将可校验输出文件的“机构”列精确同步为规则主表机构名称。"""
    header, rows, line_ending = read_output_rows(path)
    if header.count(OUTPUT_INSTITUTION_HEADER) != 1:
        return False, "表头未包含唯一的“机构”列"
    institution_index = header.index(OUTPUT_INSTITUTION_HEADER)
    changed_count = sum(row[institution_index] != institution for row in rows)
    if not changed_count:
        return False, "机构字段已一致"
    if not dry_run:
        for row in rows:
            row[institution_index] = institution
        content = line_ending.join(["\t".join(header), *("\t".join(row) for row in rows)]) + line_ending
        path.write_text(content, encoding="utf-8-sig", newline="")
    return True, f"已同步 {changed_count} 行“机构”字段"


def process_artifact_names(
    category: str,
    artifact_paths: dict[str, list[Path]],
    expected_names: dict[str, str],
    dry_run: bool,
) -> list[AuditItem]:
    """只在一个序号唯一对应一个文件且目标不存在时原地改名。"""
    items: list[AuditItem] = []
    for sequence, paths in sorted(artifact_paths.items()):
        expected_name = expected_names.get(sequence)
        if not expected_name:
            for path in paths:
                items.append(AuditItem(category, sequence, path, "未处理", "脚本序号不在规则主表"))
            continue
        if len(paths) != 1:
            for path in paths:
                items.append(AuditItem(category, sequence, path, "未处理", f"同一序号发现 {len(paths)} 个文件，无法唯一改名"))
            continue
        path = paths[0]
        if path.name == expected_name:
            items.append(AuditItem(category, sequence, path, "一致", "文件名已与规则主表一致"))
            continue
        target = path.with_name(expected_name)
        if target.exists():
            items.append(AuditItem(category, sequence, path, "未处理", f"目标文件已存在：{target}"))
            continue
        if not dry_run:
            path.rename(target)
        items.append(AuditItem(category, sequence, path, "将改名" if dry_run else "已改名", f"{path.name} -> {expected_name}"))
    return items


def report_missing_artifacts(
    category: str,
    artifact_paths: dict[str, list[Path]],
    expected_names: dict[str, str],
    directory: Path,
) -> list[AuditItem]:
    """报告规则主表存在、但当前目录尚未生成对应产物的记录。"""
    return [
        AuditItem(
            category,
            sequence,
            directory / expected_name,
            "缺失",
            "规则主表存在该序号，但未发现对应文件",
        )
        for sequence, expected_name in sorted(expected_names.items())
        if sequence not in artifact_paths
    ]


def process_output_institutions(
    artifact_paths: dict[str, list[Path]],
    institutions: dict[str, str],
    dry_run: bool,
) -> list[AuditItem]:
    """独立于文件名逐个更新已关联输出文件的“机构”列。"""
    items: list[AuditItem] = []
    for sequence, paths in sorted(artifact_paths.items()):
        institution = institutions.get(sequence)
        if not institution:
            continue
        for path in paths:
            try:
                changed, detail = synchronize_output_institution(path, institution, dry_run)
            except ValueError as error:
                items.append(AuditItem("输出机构字段", sequence, path, "未处理", str(error)))
                continue
            status = ("将更新" if dry_run else "已更新") if changed else "一致"
            items.append(AuditItem("输出机构字段", sequence, path, status, detail))
    return items


def write_report(items: list[AuditItem], report_path: Path, dry_run: bool) -> None:
    """输出 UTF-8 TSV 审计报告。"""
    summary: dict[tuple[str, str], int] = defaultdict(int)
    for item in items:
        summary[(item.category, item.status)] += 1
    lines = [
        "规则主表命名与机构字段同步审计报告",
        f"执行模式：{'仅检查' if dry_run else '已执行同步'}",
        "",
        "类别\t状态\t数量",
        *(f"{category}\t{status}\t{count}" for (category, status), count in sorted(summary.items())),
        "",
        "类别\t脚本序号\t文件\t状态\t说明",
    ]
    lines.extend(
        f"{item.category}\t{item.sequence}\t{item.path}\t{item.status}\t{item.detail}"
        for item in items
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(dry_run: bool) -> None:
    """执行主表驱动的命名与机构字段同步。"""
    rule_table_path = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    adapter_dir = resolve_project_path("important_people/site_adapters", anchor=__file__, must_exist=True)
    outputs_dir = resolve_project_path("important_people/outputs", anchor=__file__, must_exist=True)
    reports_dir = resolve_project_path("important_people/workspace/reports", anchor=__file__, must_exist=True)
    log_dir = resolve_project_path("important_people/workspace/log", anchor=__file__, must_exist=True)

    rules = load_rule_table(rule_table_path)
    institutions = {rule["脚本序号"]: rule["机构名称"] for rule in rules}
    expected_script_names = {sequence: build_script_name(sequence, name) for sequence, name in institutions.items()}
    expected_output_names = {sequence: build_output_name(sequence, name) for sequence, name in institutions.items()}
    scripts = collect_artifacts(adapter_dir, ".py")
    outputs = collect_artifacts(outputs_dir, ".txt")

    items = process_artifact_names("页面脚本", scripts, expected_script_names, dry_run)
    items.extend(report_missing_artifacts("页面脚本", scripts, expected_script_names, adapter_dir))
    items.extend(process_artifact_names("输出文件", outputs, expected_output_names, dry_run))
    items.extend(report_missing_artifacts("输出文件", outputs, expected_output_names, outputs_dir))
    output_paths_for_content = outputs if dry_run else collect_artifacts(outputs_dir, ".txt")
    items.extend(process_output_institutions(output_paths_for_content, institutions, dry_run))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "预检" if dry_run else "同步"
    report_path = reports_dir / f"规则主表命名与机构字段{mode}审计_{timestamp}.txt"
    log_path = log_dir / f"规则主表命名与机构字段{mode}_{timestamp}.log"
    write_report(items, report_path, dry_run)
    changed = sum(item.status in {"将改名", "已改名", "将更新", "已更新"} for item in items)
    log_message = f"规则记录 {len(rules)} 条；脚本 {sum(map(len, scripts.values()))} 个；输出 {sum(map(len, outputs.values()))} 个；变动项 {changed} 个；报告：{report_path}"
    log_path.write_text(log_message + "\n", encoding="utf-8")
    print(log_message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="按规则主表同步页面脚本、输出命名和机构字段")
    parser.add_argument("--dry-run", action="store_true", help="只生成审计结果，不改动文件")
    arguments = parser.parse_args()
    main(arguments.dry_run)
