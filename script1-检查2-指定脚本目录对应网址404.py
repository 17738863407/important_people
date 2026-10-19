from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
import re

from crawler_core.rule_table import load_rule_table
from crawler_core.paths import resolve_path_argument


# 文件名包含连字符，使用 importlib 按模块名动态加载。
source_url_checker = import_module("script1-检查1-源数据网址404")
DualLogger = source_url_checker.DualLogger
UrlCheckResult = source_url_checker.UrlCheckResult
check_unique_urls = source_url_checker.check_unique_urls
normalize_url = source_url_checker.normalize_url
should_export_result = source_url_checker.should_export_result


@dataclass(frozen=True)
class ScriptFileRecord:
    """保存递归扫描到的页面脚本及其四位脚本序号。"""

    rule_id: str
    relative_path: str


@dataclass(frozen=True)
class SelectedUrlRecord:
    """保存脚本文件与规则主表中对应网址之间的可回溯关系。"""

    script_relative_path: str
    source_name: str
    source_row_number: int
    rule_id: str
    organization: str
    original_url: str
    normalized_url: str


@dataclass(frozen=True)
class SelectionIssue:
    """保存脚本筛选阶段发现的文件名或规则主表问题。"""

    script_relative_path: str
    rule_id: str
    status_label: str
    review_note: str


def scan_script_files(
    script_dir: Path,
    max_scripts: int | None,
    logger: DualLogger,
) -> tuple[list[ScriptFileRecord], list[SelectionIssue]]:
    """递归扫描Python脚本，并从标准文件名开头提取四位脚本序号。"""
    if not script_dir.is_dir():
        raise NotADirectoryError(f"脚本目录不存在或不是文件夹：{script_dir}")

    script_records: list[ScriptFileRecord] = []
    issues: list[SelectionIssue] = []
    script_paths = sorted(
        (
            path
            for path in script_dir.rglob("*.py")
            if "__pycache__" not in path.parts
        ),
        key=lambda path: str(path).casefold(),
    )

    if max_scripts is not None:
        script_paths = script_paths[:max_scripts]
        logger.info(f"已按参数限制最多扫描脚本数：{max_scripts}")

    for script_path in script_paths:
        relative_path = str(script_path.relative_to(script_dir))
        rule_id_match = re.match(r"^(\d{4})(?:_|$)", script_path.stem)
        if rule_id_match is None:
            issues.append(
                SelectionIssue(
                    script_relative_path=relative_path,
                    rule_id="",
                    status_label="脚本名异常",
                    review_note="文件名未以四位脚本序号加下划线开头，无法关联规则主表",
                )
            )
            continue
        script_records.append(
            ScriptFileRecord(
                rule_id=rule_id_match.group(1),
                relative_path=relative_path,
            )
        )

    duplicate_groups: dict[str, list[str]] = {}
    for script_record in script_records:
        duplicate_groups.setdefault(script_record.rule_id, []).append(script_record.relative_path)
    duplicate_groups = {
        rule_id: paths
        for rule_id, paths in duplicate_groups.items()
        if len(paths) > 1
    }

    logger.info(f"递归发现Python脚本：{len(script_paths)}")
    logger.info(f"成功识别脚本序号：{len(script_records)}")
    logger.info(f"无法识别序号的脚本：{len(issues)}")
    logger.info(f"重复脚本序号组数：{len(duplicate_groups)}")
    for rule_id, paths in sorted(duplicate_groups.items()):
        logger.info(f"发现重复脚本序号 {rule_id}：{'；'.join(paths)}")
    return script_records, issues


def select_url_records(
    rule_table_path: Path,
    script_records: list[ScriptFileRecord],
    logger: DualLogger,
) -> tuple[list[SelectedUrlRecord], list[SelectionIssue]]:
    """只选择扫描所得脚本序号在规则主表中对应的网址记录。"""
    scripts_by_rule_id: dict[str, list[ScriptFileRecord]] = {}
    for script_record in script_records:
        scripts_by_rule_id.setdefault(script_record.rule_id, []).append(script_record)

    source_by_rule_id: dict[str, tuple[int, dict[str, str]]] = {}
    for row_number, source_record in enumerate(load_rule_table(rule_table_path), start=2):
        rule_id = str(source_record.get("脚本序号", "")).strip()
        if rule_id in scripts_by_rule_id:
            source_by_rule_id[rule_id] = (row_number, source_record)

    selected_records: list[SelectedUrlRecord] = []
    issues: list[SelectionIssue] = []
    for rule_id, matching_scripts in sorted(scripts_by_rule_id.items()):
        source_item = source_by_rule_id.get(rule_id)
        if source_item is None:
            for script_record in matching_scripts:
                issues.append(
                    SelectionIssue(
                        script_relative_path=script_record.relative_path,
                        rule_id=rule_id,
                        status_label="规则缺失",
                        review_note="规则主表中找不到该脚本序号",
                    )
                )
            continue

        row_number, source_record = source_item
        original_url = str(source_record.get("领导链接", "")).strip()
        normalized_url = normalize_url(original_url)
        if not normalized_url:
            for script_record in matching_scripts:
                issues.append(
                    SelectionIssue(
                        script_relative_path=script_record.relative_path,
                        rule_id=rule_id,
                        status_label="网址为空",
                        review_note="规则主表对应记录的依据链接为空",
                    )
                )
            continue

        for script_record in matching_scripts:
            selected_records.append(
                SelectedUrlRecord(
                    script_relative_path=script_record.relative_path,
                    source_name=rule_table_path.name,
                    source_row_number=row_number,
                    rule_id=rule_id,
                organization=str(source_record.get("机构名称", "")).strip(),
                    original_url=original_url,
                    normalized_url=normalized_url,
                )
            )

    logger.info(f"与规则主表成功关联的网址记录：{len(selected_records)}")
    logger.info(f"筛选阶段问题记录：{len(issues)}")
    return selected_records, issues


def clean_cell(value: object) -> str:
    """清除制表符和换行，保证TXT报告保持严格的TSV结构。"""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def build_result_sort_key(
    record: SelectedUrlRecord,
    result: UrlCheckResult,
) -> tuple[int, int, str, str]:
    """优先按HTTP状态码排序，其次按脚本序号和脚本路径排序。"""
    if result.http_status.isdigit():
        status_group = 0
        status_code = int(result.http_status)
    else:
        status_group = 1
        status_code = 999999
    return status_group, status_code, record.rule_id, record.script_relative_path


def write_report(
    report_path: Path,
    records: list[SelectedUrlRecord],
    issues: list[SelectionIssue],
    results: dict[str, UrlCheckResult],
    only_problem_rows: bool,
) -> int:
    """导出网址检查结果及无法进入联网检查阶段的筛选问题。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "检查时间",
        "判定",
        "HTTP状态",
        "请求方法",
        "脚本相对路径",
        "规则源文件",
        "规则源行号",
        "脚本序号",
        "机构",
        "原始网址",
        "最终网址",
        "重定向次数",
        "响应毫秒",
        "响应字节数",
        "内容类型",
        "页面标题",
        "复核说明",
        "错误类型",
        "错误信息",
    ]
    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_rows: list[tuple[tuple[int, int, str, str], list[str]]] = []

    for record in records:
        result = results.get(record.normalized_url)
        if result is None or not should_export_result(result.status_label, only_problem_rows):
            continue
        row = [
            export_time,
            result.status_label,
            result.http_status,
            result.request_method,
            record.script_relative_path,
            record.source_name,
            record.source_row_number,
            record.rule_id,
            record.organization,
            record.original_url,
            result.final_url,
            result.redirect_count,
            result.elapsed_ms,
            result.response_bytes,
            result.content_type,
            result.page_title,
            result.review_note,
            result.error_type,
            result.error_message,
        ]
        report_rows.append(
            (
                build_result_sort_key(record=record, result=result),
                [clean_cell(value) for value in row],
            )
        )

    for issue in issues:
        issue_row = [
            export_time,
            issue.status_label,
            "",
            "",
            issue.script_relative_path,
            "",
            "",
            issue.rule_id,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            issue.review_note,
            "",
            "",
        ]
        report_rows.append(((2, 999999, issue.rule_id, issue.script_relative_path), issue_row))

    with report_path.open("w", encoding="utf-8") as file:
        file.write("\t".join(headers) + "\n")
        for _, row in sorted(report_rows, key=lambda item: item[0]):
            file.write("\t".join(row) + "\n")
    return len(report_rows)


def summarize_results(
    records: list[SelectedUrlRecord],
    issues: list[SelectionIssue],
    results: dict[str, UrlCheckResult],
) -> dict[str, int]:
    """统计联网检查结果和筛选问题，便于从日志快速掌握整体情况。"""
    summary: dict[str, int] = {}
    for record in records:
        result = results.get(record.normalized_url)
        label = result.status_label if result is not None else "未检查"
        summary[label] = summary.get(label, 0) + 1
    for issue in issues:
        summary[issue.status_label] = summary.get(issue.status_label, 0) + 1
    return summary


def main(
    script_dir: str | Path,
    rule_table_path: str | Path,
    report_path: str | Path,
    log_path: str | Path,
    timeout_seconds: int,
    retry_times: int,
    verify_ssl: bool,
    use_system_proxy: bool,
    fallback_get_status_codes: set[int],
    workers: int,
    only_problem_rows: bool,
    max_scripts: int | None,
) -> None:
    """递归扫描指定目录，只检查这些脚本在规则主表中对应的网址。"""
    script_dir = resolve_path_argument(script_dir, anchor=__file__, must_exist=True)
    rule_table_path = resolve_path_argument(
        rule_table_path, anchor=__file__, must_exist=True
    )
    report_path = resolve_path_argument(report_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    logger = DualLogger(log_path=log_path)
    logger.info(f"开始递归扫描脚本目录：{script_dir}")
    script_records, scan_issues = scan_script_files(
        script_dir=script_dir,
        max_scripts=max_scripts,
        logger=logger,
    )

    logger.info(f"开始按脚本序号查询权威规则主表：{rule_table_path}")
    selected_records, selection_issues = select_url_records(
        rule_table_path=rule_table_path,
        script_records=script_records,
        logger=logger,
    )
    all_issues = scan_issues + selection_issues
    unique_urls = sorted({record.normalized_url for record in selected_records})
    logger.info(f"待检查网址记录数：{len(selected_records)}")
    logger.info(f"去重后实际联网检查网址数：{len(unique_urls)}")

    results = check_unique_urls(
        urls=unique_urls,
        timeout_seconds=timeout_seconds,
        retry_times=retry_times,
        verify_ssl=verify_ssl,
        use_system_proxy=use_system_proxy,
        fallback_get_status_codes=fallback_get_status_codes,
        workers=workers,
    )
    exported_count = write_report(
        report_path=report_path,
        records=selected_records,
        issues=all_issues,
        results=results,
        only_problem_rows=only_problem_rows,
    )
    summary = summarize_results(
        records=selected_records,
        issues=all_issues,
        results=results,
    )

    for label, count in sorted(summary.items()):
        logger.info(f"结果统计：{label} = {count}")
    logger.info(f"已导出报告行数：{exported_count}")
    logger.info(f"报告路径：{report_path}")
    logger.info(f"日志路径：{log_path}")


if __name__ == "__main__":
    current_time_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir_value = r"important_people/site_adapters/成功"
    rule_table_path_value = r"important_people/workspace/source_data/规则主表.txt"
    report_path_value = rf"important_people/workspace/reports/指定脚本目录网址状态检查_{current_time_value}.txt"
    log_path_value = rf"important_people/workspace/log/指定脚本目录网址状态检查_{current_time_value}.log"
    timeout_seconds_value = 8
    retry_times_value = 0
    verify_ssl_value = True
    use_system_proxy_value = False
    fallback_get_status_codes_value = {400, 403, 404, 405, 406, 410, 429, 500, 501, 503}
    workers_value = 48
    only_problem_rows_value = True
    max_scripts_value = None
    main(
        script_dir=script_dir_value,
        rule_table_path=rule_table_path_value,
        report_path=report_path_value,
        log_path=log_path_value,
        timeout_seconds=timeout_seconds_value,
        retry_times=retry_times_value,
        verify_ssl=verify_ssl_value,
        use_system_proxy=use_system_proxy_value,
        fallback_get_status_codes=fallback_get_status_codes_value,
        workers=workers_value,
        only_problem_rows=only_problem_rows_value,
        max_scripts=max_scripts_value,
    )
