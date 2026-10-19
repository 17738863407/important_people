"""将确认后的省市映射写回规则主表，并同步更新十二列合并结果。"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


def log_message(message: str, log_path: Path) -> None:
    """同时向控制台和日志文件输出执行信息。"""
    print(message)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(f"{message}\n")


def calculate_sha256(file_path: Path) -> str:
    """计算文件哈希，用于写入前后审计。"""
    digest = hashlib.sha256()
    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_tsv(file_path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    """读取UTF-8制表符文本，并严格检查表头与列数。"""
    lines = file_path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{file_path}")
    header = lines[0].split("\t")
    if header != expected_header:
        raise ValueError(f"表头不符合预期：{file_path}；实际为{header}")

    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ValueError(f"{file_path}第{line_number}行列数异常：{len(cells)}")
        rows.append(dict(zip(header, cells, strict=True)))
    return rows


def serialize_tsv(header: list[str], rows: Iterable[dict[str, str]]) -> str:
    """把记录序列化为UTF-8制表符文本内容。"""
    lines = ["\t".join(header)]
    for row in rows:
        cells = [str(row.get(column, "")) for column in header]
        if any("\t" in cell or "\r" in cell or "\n" in cell for cell in cells):
            raise ValueError(f"记录包含制表符或换行，不能安全写入：{row}")
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n"


def atomic_write_text(file_path: Path, content: str) -> None:
    """先写入同目录临时文件，再原子替换目标文件。"""
    temp_path = file_path.with_name(f".{file_path.name}.codex_tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, file_path)


def make_unique_index(rows: list[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    """按指定字段建立唯一索引，发现空值或重复立即停止。"""
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value:
            raise ValueError(f"{label}存在空{key}")
        if value in index:
            raise ValueError(f"{label}存在重复{key}：{value}")
        index[value] = row
    return index


def validate_mapping(
    main_rows: list[dict[str, str]],
    mapping_rows: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """验证地域映射与规则主表的脚本序号、机构名称一一对应。"""
    main_by_id = make_unique_index(main_rows, "脚本序号", "规则主表")
    mapping_by_id = make_unique_index(mapping_rows, "脚本序号", "省市映射")
    if set(main_by_id) != set(mapping_by_id):
        missing = sorted(set(main_by_id) - set(mapping_by_id))
        extra = sorted(set(mapping_by_id) - set(main_by_id))
        raise ValueError(f"省市映射与规则主表脚本序号不一致；缺少={missing[:10]}，多出={extra[:10]}")

    for rule_id, main_row in main_by_id.items():
        mapping_row = mapping_by_id[rule_id]
        if main_row["机构名称"] != mapping_row["机构"]:
            raise ValueError(
                f"机构名称不一致：{rule_id}；主表={main_row['机构名称']}；映射={mapping_row['机构']}"
            )
        if not mapping_row["所属省*"]:
            raise ValueError(f"确认后的映射仍有空省：{rule_id} {mapping_row['机构']}")
        if mapping_row["所属省*"] == "全国" and mapping_row["所属市"]:
            raise ValueError(f"全国机构不应填写所属市：{rule_id} {mapping_row['机构']}")
    return main_by_id, mapping_by_id


def build_main_rows(
    main_by_id: dict[str, dict[str, str]],
    mapping_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """按照规则主表现有机构目录顺序写入省市，不再按省市映射重排。"""
    result: list[dict[str, str]] = []
    mapping_by_id = make_unique_index(mapping_rows, "脚本序号", "省市映射")
    for rule_id, main_row in main_by_id.items():
        mapping_row = mapping_by_id[rule_id]
        row = main_row.copy()
        row["所属省*"] = mapping_row["所属省*"]
        row["所属市"] = mapping_row["所属市"]
        result.append(row)
    return result


def build_merged_rows(
    merged_rows: list[dict[str, str]],
    mapping_by_id: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], Counter[str]]:
    """按脚本序号同步人物结果，保持原有记录顺序和其他字段不变。"""
    result: list[dict[str, str]] = []
    province_counts: Counter[str] = Counter()
    for row in tqdm(merged_rows, desc="同步合并结果省市", unit="条"):
        rule_id = row["脚本序号"]
        if rule_id not in mapping_by_id:
            raise ValueError(f"合并结果存在未知脚本序号：{rule_id}")
        mapping_row = mapping_by_id[rule_id]
        if row["机构"] != mapping_row["机构"]:
            raise ValueError(
                f"合并结果机构不一致：{rule_id}；结果={row['机构']}；映射={mapping_row['机构']}"
            )
        updated = row.copy()
        updated["所属省*"] = mapping_row["所属省*"]
        updated["所属市"] = mapping_row["所属市"]
        result.append(updated)
        province_counts[updated["所属省*"]] += 1
    return result, province_counts


def validate_non_location_fields(
    before_rows: list[dict[str, str]],
    after_rows: list[dict[str, str]],
    header: list[str],
    label: str,
) -> None:
    """验证除所属省市外的字段和记录顺序均未发生变化。"""
    if len(before_rows) != len(after_rows):
        raise ValueError(f"{label}写入前后记录数不一致")
    stable_columns = [column for column in header if column not in {"所属省*", "所属市"}]
    for row_number, (before, after) in enumerate(zip(before_rows, after_rows, strict=True), start=2):
        for column in stable_columns:
            if before[column] != after[column]:
                raise ValueError(f"{label}第{row_number}行非地域字段被改动：{column}")


def write_report(
    report_path: Path,
    timestamp: str,
    mapping_path: Path,
    main_path: Path,
    merged_path: Path,
    main_backup: Path,
    merged_backup: Path,
    main_count: int,
    merged_count: int,
    province_counts: Counter[str],
    hashes: dict[str, str],
) -> None:
    """生成本次正式写入的审计报告。"""
    lines = [
        "规则主表与合并结果省市写入报告",
        f"执行时间\t{timestamp}",
        f"确认映射\t{mapping_path}",
        f"规则主表\t{main_path}",
        f"合并结果\t{merged_path}",
        f"规则主表备份\t{main_backup}",
        f"合并结果备份\t{merged_backup}",
        f"规则主表记录数\t{main_count}",
        f"合并人物记录数\t{merged_count}",
        f"规则主表写入前SHA256\t{hashes['main_before']}",
        f"规则主表写入后SHA256\t{hashes['main_after']}",
        f"合并结果写入前SHA256\t{hashes['merged_before']}",
        f"合并结果写入后SHA256\t{hashes['merged_after']}",
        "",
        "合并人物记录归属统计",
        "所属省*\t人物记录数",
    ]
    lines.extend(f"{province}\t{count}" for province, count in province_counts.most_common())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(
    main_path: Path,
    mapping_path: Path,
    merged_path: Path,
    backup_dir: Path,
    report_path: Path,
    log_dir: Path,
    main_header: list[str],
    mapping_header: list[str],
    merged_header: list[str],
) -> None:
    """完成备份、写入、回读验证和报告生成。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    readable_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"规则主表与合并结果省市写入_{timestamp}.log"

    main_rows = read_tsv(main_path, main_header)
    mapping_rows = read_tsv(mapping_path, mapping_header)
    merged_rows = read_tsv(merged_path, merged_header)
    main_by_id, mapping_by_id = validate_mapping(main_rows, mapping_rows)

    main_backup = backup_dir / f"规则主表_写入省市前备份_{timestamp}.txt"
    merged_backup = backup_dir / f"合并txt结果_test_写入省市前备份_{timestamp}.txt"
    hashes = {
        "main_before": calculate_sha256(main_path),
        "merged_before": calculate_sha256(merged_path),
    }
    shutil.copy2(main_path, main_backup)
    shutil.copy2(merged_path, merged_backup)
    log_message(f"已备份规则主表：{main_backup}", log_path)
    log_message(f"已备份合并结果：{merged_backup}", log_path)

    updated_main_rows = build_main_rows(main_by_id, mapping_rows)
    updated_merged_rows, province_counts = build_merged_rows(merged_rows, mapping_by_id)
    atomic_write_text(main_path, serialize_tsv(main_header, updated_main_rows))
    atomic_write_text(merged_path, serialize_tsv(merged_header, updated_merged_rows))

    written_main_rows = read_tsv(main_path, main_header)
    written_merged_rows = read_tsv(merged_path, merged_header)
    validate_mapping(written_main_rows, mapping_rows)
    validate_non_location_fields(merged_rows, written_merged_rows, merged_header, "合并结果")
    if [row["脚本序号"] for row in written_main_rows] != [row["脚本序号"] for row in mapping_rows]:
        raise ValueError("规则主表未保持确认映射的归属排序")
    for row in written_merged_rows:
        mapping_row = mapping_by_id[row["脚本序号"]]
        if row["所属省*"] != mapping_row["所属省*"] or row["所属市"] != mapping_row["所属市"]:
            raise ValueError(f"合并结果省市未正确同步：{row['脚本序号']}")

    hashes["main_after"] = calculate_sha256(main_path)
    hashes["merged_after"] = calculate_sha256(merged_path)
    write_report(
        report_path,
        readable_timestamp,
        mapping_path,
        main_path,
        merged_path,
        main_backup,
        merged_backup,
        len(written_main_rows),
        len(written_merged_rows),
        province_counts,
        hashes,
    )
    log_message(f"规则主表已正式写入：{len(written_main_rows)}条", log_path)
    log_message(f"合并结果已同步：{len(written_merged_rows)}条", log_path)
    log_message(f"审计报告：{report_path}", log_path)


if __name__ == "__main__":
    rule_main_file = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    confirmed_mapping_file = resolve_project_path(
        "important_people/规则主表-省市推断副本.txt", anchor=__file__, must_exist=True
    )
    merged_result_file = resolve_project_path(
        "important_people/合并txt结果_test.txt", anchor=__file__, must_exist=True
    )
    backup_folder = resolve_project_path("important_people/workspace/reports/backups", anchor=__file__)
    audit_report_file = resolve_project_path(
        "important_people/workspace/reports/规则主表与合并结果省市写入报告.txt", anchor=__file__
    )
    execution_log_folder = resolve_project_path("important_people/workspace/log", anchor=__file__)
    rule_main_header = [
        "组织体系", "目录链接", "机构类型", "机构层级", "所属省*", "所属市",
        "机构名称", "机构别称", "官网链接", "领导链接", "脚本序号", "备注",
    ]
    confirmed_mapping_header = ["脚本序号", "机构", "所属省*", "所属市"]
    merged_result_header = [
        "姓名*", "职务*", "排序*", "职级*", "所属省*", "所属市", "依据链接",
        "依据说明", "维护人", "机构", "详情页链接", "脚本序号",
    ]
    main(
        rule_main_file,
        confirmed_mapping_file,
        merged_result_file,
        backup_folder,
        audit_report_file,
        execution_log_folder,
        rule_main_header,
        confirmed_mapping_header,
        merged_result_header,
    )
