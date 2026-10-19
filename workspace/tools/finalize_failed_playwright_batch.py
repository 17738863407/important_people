from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_external_path, resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_external_path, resolve_project_path


OUTPUT_HEADER = [
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


def read_tsv(path: Path) -> list[list[str]]:
    """读取 UTF-8 TSV，保留空字段。"""
    return [line.split("\t") for line in path.read_text(encoding="utf-8-sig").splitlines()]


def copy_confirmed_failure(source_path: Path, failure_dir: Path) -> Path:
    """并入已实际运行、但因沙箱域名误判而从本轮排除的 1148 结果。"""
    target_path = failure_dir / source_path.name
    shutil.copy2(source_path, target_path)
    return target_path


def normalize_failure_evidence(failure_dir: Path) -> list[str]:
    """为已识别姓名但缺少可回指职务证据的失败行补写明确失败说明。"""
    changed_files: list[str] = []
    for path in sorted(failure_dir.glob("*.txt")):
        rows = read_tsv(path)
        changed = False
        for row in rows[1:]:
            if len(row) == len(OUTPUT_HEADER) and row[0].strip() and not row[7].strip():
                row[7] = "抽取失败：已识别人物姓名，但当前页面未提取到可回指的职务依据说明"
                changed = True
        if changed:
            path.write_text("\n".join("\t".join(row) for row in rows) + "\n", encoding="utf-8")
            changed_files.append(path.name)
    return changed_files


def validate_outputs(
    expected: set[str],
    success_dir: Path,
    failure_dir: Path,
) -> tuple[list[str], list[str], Counter[str], list[str]]:
    """核对覆盖范围、十二列结构及成功/失败记录的基本质量门禁。"""
    success_files = sorted(success_dir.glob("*.txt"))
    failure_files = sorted(failure_dir.glob("*.txt"))
    actual_files = success_files + failure_files
    actual_sequences = [path.name[:4] for path in actual_files]
    counts = Counter(actual_sequences)
    problems: list[str] = []
    warnings: list[str] = []
    missing = sorted(expected - set(actual_sequences))
    extra = sorted(set(actual_sequences) - expected)
    duplicates = sorted(sequence for sequence, count in counts.items() if count != 1)
    if missing:
        problems.append("缺少脚本序号：" + ",".join(missing))
    if extra:
        problems.append("多余脚本序号：" + ",".join(extra))
    if duplicates:
        problems.append("重复脚本序号：" + ",".join(duplicates))

    collector_counts: Counter[str] = Counter()
    for path in actual_files:
        rows = read_tsv(path)
        if not rows or rows[0] != OUTPUT_HEADER:
            problems.append(f"表头不符合十二列契约：{path.name}")
            continue
        if len(rows) < 2:
            problems.append(f"没有数据行：{path.name}")
            continue
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != len(OUTPUT_HEADER):
                problems.append(f"列数不是12：{path.name}:{line_number}={len(row)}")
                continue
            if row[11] != path.name[:4]:
                problems.append(f"脚本序号字段与文件名不一致：{path.name}:{line_number}")
            if not row[6].strip():
                if path.parent == failure_dir and row[7].strip().startswith("抽取失败"):
                    warnings.append(f"权威入口为空，已保留失败说明：{path.name}:{line_number}")
                else:
                    problems.append(f"依据链接为空：{path.name}:{line_number}")
        if path.parent == success_dir:
            valid_rows = [
                row
                for row in rows[1:]
                if len(row) == len(OUTPUT_HEADER) and row[0].strip() and row[7].strip()
            ]
            if not valid_rows:
                problems.append(f"成功文件缺少姓名或依据说明：{path.name}")
            if len(valid_rows) > 100:
                warnings.append(f"人物记录数异常偏多，需人工复核：{path.name}={len(valid_rows)}")
        else:
            if not all(
                len(row) == len(OUTPUT_HEADER) and row[7].strip().startswith("抽取失败")
                for row in rows[1:]
            ):
                problems.append(f"失败文件未保留明确失败原因：{path.name}")

    return problems, warnings, collector_counts, sorted(expected)


def read_report_data_rows(path: Path) -> tuple[str, list[str]]:
    """读取报告首个表格区域。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = lines[0]
    rows: list[str] = []
    for line in lines[1:]:
        if not line:
            break
        rows.append(line)
    return header, rows


def expected_sequences_from_reports(success_report: Path, failure_report: Path) -> set[str]:
    """从本次运行器报告恢复已执行清单，避免依赖运行后被外部移走的源目录。"""
    expected: set[str] = {"1148"}
    for report_path in (success_report, failure_report):
        _, rows = read_report_data_rows(report_path)
        expected.update(
            row.split("\t", 1)[0]
            for row in rows
            if row.split("\t", 1)[0].isdigit()
        )
    return expected


def write_final_reports(
    generated_success_report: Path,
    generated_failure_report: Path,
    final_success_report: Path,
    final_failure_report: Path,
    audit_report: Path,
    success_dir: Path,
    failure_dir: Path,
    problems: list[str],
    warnings: list[str],
) -> None:
    """生成本批次稳定命名的成功、失败和验收报告。"""
    shutil.copy2(generated_success_report, final_success_report)
    failure_header, failure_rows = read_report_data_rows(generated_failure_report)
    failure_rows.append(
        "1148\t贵阳市公安交通管理局\t"
        "http://jjzd.guiyang.gov.cn/zwgk/zfxxgk/fdzdgknr/fdzdgknrjggk/ldzc/\t"
        "抽取失败：站点域名当前无法解析，代理返回 502 Bad Gateway；该网址曾触发沙箱私网误判，"
        "已按实际联网结果保留失败。"
    )
    failure_rows.sort(key=lambda line: line.split("\t", 1)[0])
    final_failure_report.write_text(
        "\n".join(
            [
                failure_header,
                *failure_rows,
                "",
                "采集统计\t值",
                f"失败脚本数\t{len(failure_rows)}",
                "补入已执行脚本\t1148_贵阳市公安交通管理局",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    success_count = len(list(success_dir.glob("*.txt")))
    failure_count = len(list(failure_dir.glob("*.txt")))
    audit_lines = [
        "项目\t结果",
        "输入TXT数\t654",
        "无有效脚本TXT\t0000_页面.txt",
        f"可运行脚本覆盖数\t{success_count + failure_count}",
        f"成功文件数\t{success_count}",
        f"失败文件数\t{failure_count}",
        f"十二列及基础质量问题数\t{len(problems)}",
        f"人工复核提示数\t{len(warnings)}",
    ]
    audit_lines.extend(f"质量问题\t{item}" for item in problems)
    audit_lines.extend(f"人工复核\t{item}" for item in warnings)
    audit_report.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")


def main(
    source_dir: Path,
    partial_1148_path: Path,
    batch_output_dir: Path,
    generated_success_report: Path,
    generated_failure_report: Path,
    report_dir: Path,
) -> None:
    """合并 1148 并完成最终批次验收。"""
    success_dir = batch_output_dir / "成功"
    failure_dir = batch_output_dir / "失败"
    copy_confirmed_failure(partial_1148_path, failure_dir)
    normalized_failure_files = normalize_failure_evidence(failure_dir)
    expected_sequences = expected_sequences_from_reports(
        generated_success_report,
        generated_failure_report,
    )
    problems, warnings, _, _ = validate_outputs(expected_sequences, success_dir, failure_dir)
    if normalized_failure_files:
        warnings.append(
            "以下失败文件已补写‘缺少可回指职务依据说明’：" + ",".join(normalized_failure_files)
        )
    write_final_reports(
        generated_success_report=generated_success_report,
        generated_failure_report=generated_failure_report,
        final_success_report=report_dir / "失败目录Playwright完整重跑_20261004_成功采集报告.txt",
        final_failure_report=report_dir / "失败目录Playwright完整重跑_20261004_失败报告.txt",
        audit_report=report_dir / "失败目录Playwright完整重跑_20261004_验收报告.txt",
        success_dir=success_dir,
        failure_dir=failure_dir,
        problems=problems,
        warnings=warnings,
    )
    if problems:
        raise RuntimeError("最终验收发现问题：" + "；".join(problems))


if __name__ == "__main__":
    project_root_value = resolve_project_path("important_people", anchor=__file__)
    source_dir_value = resolve_external_path("IMPORTANT_PERSON_FAILED_DIR")
    partial_1148_path_value = (
        project_root_value / "outputs" / "失败目录Playwright重跑_20261004" / "1148_贵阳市公安交通管理局.txt"
    )
    batch_output_dir_value = project_root_value / "outputs" / "失败目录Playwright完整重跑_20261004"
    generated_success_report_value = (
        project_root_value / "workspace" / "reports" / "一键运行全部爬虫脚本_成功采集报告_20261004_214643.txt"
    )
    generated_failure_report_value = (
        project_root_value / "workspace" / "reports" / "一键运行全部爬虫脚本_失败报告_20261004_214643.txt"
    )
    report_dir_value = project_root_value / "workspace" / "reports"
    main(
        source_dir_value,
        partial_1148_path_value,
        batch_output_dir_value,
        generated_success_report_value,
        generated_failure_report_value,
        report_dir_value,
    )
