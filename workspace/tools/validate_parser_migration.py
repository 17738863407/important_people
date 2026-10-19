from __future__ import annotations

import ast
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


@dataclass
class ParserReference:
    """记录脚本中引用解析器的位置。"""

    script_path: Path
    field_name: str
    raw_name: str
    normalized_name: str
    status: str


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台和日志文件。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def iter_progress(items: list[Path], description: str) -> Iterable[Path]:
    """优先使用 tqdm 展示进度，缺失时退化为普通迭代。"""
    try:
        from tqdm import tqdm

        return tqdm(items, desc=description, unit="个")
    except Exception:
        return items


def find_page_rule(script_path: Path) -> tuple[dict | None, str]:
    """从脚本中提取 PAGE_RULE。"""
    try:
        text = script_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
    except Exception as error:
        return None, f"AST 解析失败：{error}"

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "PAGE_RULE" for target in node.targets):
            try:
                page_rule = ast.literal_eval(node.value)
            except Exception as error:
                return None, f"PAGE_RULE literal_eval 失败：{error}"
            if not isinstance(page_rule, dict):
                return None, "PAGE_RULE 不是 dict"
            return page_rule, ""
    return None, "PAGE_RULE 缺失"


def collect_script_paths(adapter_dirs: list[Path]) -> list[Path]:
    """收集需要校验的脚本路径。"""
    script_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for adapter_dir in adapter_dirs:
        if not adapter_dir.exists():
            continue
        for script_path in sorted(adapter_dir.glob("*.py")):
            resolved_path = script_path.resolve()
            if resolved_path not in seen_paths:
                seen_paths.add(resolved_path)
                script_paths.append(script_path)
    return script_paths


def classify_parser_name(parser_name: str, parser_registry: dict, resolve_parser_name) -> tuple[str, str]:
    """判断解析器名称是否为正式 V/S 名称。"""
    raw_name = str(parser_name or "").strip()
    if not raw_name:
        raw_name = "V001_css_field_pair_v1"
    normalized_name = resolve_parser_name(raw_name)
    if normalized_name == "skip":
        return normalized_name, "跳过"
    if normalized_name in parser_registry:
        return normalized_name, "正式名称"
    return normalized_name, "未注册"


def collect_parser_references(
    script_paths: list[Path],
    parser_registry: dict,
    resolve_parser_name,
    log_path: Path,
) -> tuple[list[ParserReference], list[str], Counter[str], Counter[str]]:
    """收集并校验 parser 引用。"""
    references: list[ParserReference] = []
    page_rule_errors: list[str] = []
    total_counter: Counter[str] = Counter()
    success_counter: Counter[str] = Counter()

    for script_path in iter_progress(script_paths, "校验 PAGE_RULE"):
        page_rule, error_message = find_page_rule(script_path)
        if page_rule is None:
            page_rule_errors.append(f"{script_path}\t{error_message}")
            continue
        is_success_script = "成功" in script_path.parts
        raw_name = str(page_rule.get("parser", "") or "").strip()
        normalized_name, status = classify_parser_name(raw_name, parser_registry, resolve_parser_name)
        references.append(
            ParserReference(
                script_path=script_path,
                field_name="parser",
                raw_name=raw_name,
                normalized_name=normalized_name,
                status=status,
            )
        )
        total_counter[normalized_name] += 1
        if is_success_script:
            success_counter[normalized_name] += 1

    write_log(log_path, f"已校验脚本数：{len(script_paths)}")
    write_log(log_path, f"已发现解析器引用数：{len(references)}")
    write_log(log_path, f"PAGE_RULE 异常数：{len(page_rule_errors)}")
    return references, page_rule_errors, total_counter, success_counter


def write_report(
    report_path: Path,
    script_paths: list[Path],
    references: list[ParserReference],
    page_rule_errors: list[str],
    total_counter: Counter[str],
    success_counter: Counter[str],
) -> None:
    """写出制表符分隔的校验报告。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved = [item for item in references if item.status == "未注册"]
    success_scripts = [path for path in script_paths if "成功" in path.parts]

    lines = [
        "项目\t数值",
        f"校验脚本总数\t{len(script_paths)}",
        f"成功目录脚本数\t{len(success_scripts)}",
        f"解析器引用总数\t{len(references)}",
        f"未注册引用数\t{len(unresolved)}",
        f"PAGE_RULE 异常数\t{len(page_rule_errors)}",
        "",
        "成功目录解析器分布\t引用次数",
    ]
    for parser_name, count in sorted(success_counter.items()):
        lines.append(f"{parser_name}\t{count}")

    lines.extend(["", "全量解析器分布\t引用次数"])
    for parser_name, count in sorted(total_counter.items()):
        lines.append(f"{parser_name}\t{count}")

    lines.extend(["", "异常类型\t文件\t字段\t原始名称\t归一名称\t状态"])
    for item in unresolved:
        lines.append(
            f"未注册\t{item.script_path}\t{item.field_name}\t{item.raw_name}\t{item.normalized_name}\t{item.status}"
        )
    for error_message in page_rule_errors:
        lines.append(f"PAGE_RULE\t{error_message}\t\t\t")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(project_dir: Path, adapter_dirs: list[Path], report_path: Path, log_path: Path) -> None:
    """脚本入口。"""
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    if log_path.exists():
        log_path.unlink()

    from crawler_core.parser_registry import PARSER_REGISTRY, resolve_parser_name

    script_paths = collect_script_paths(adapter_dirs)
    references, page_rule_errors, total_counter, success_counter = collect_parser_references(
        script_paths=script_paths,
        parser_registry=PARSER_REGISTRY,
        resolve_parser_name=resolve_parser_name,
        log_path=log_path,
    )
    write_report(
        report_path=report_path,
        script_paths=script_paths,
        references=references,
        page_rule_errors=page_rule_errors,
        total_counter=total_counter,
        success_counter=success_counter,
    )
    write_log(log_path, f"报告已生成：{report_path}")


if __name__ == "__main__":
    run_timestamp_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir_value = resolve_project_path("important_people", anchor=__file__)
    adapter_dirs_value = [
        resolve_project_path("important_people/site_adapters", anchor=__file__),
        resolve_project_path("important_people/site_adapters/成功", anchor=__file__),
    ]
    report_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/reports/解析器名称迁移校验报告.txt", anchor=__file__
    ), run_timestamp_value)
    log_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/log/解析器名称迁移校验.log", anchor=__file__
    ), run_timestamp_value)
    main(
        project_dir=project_dir_value,
        adapter_dirs=adapter_dirs_value,
        report_path=report_path_value,
        log_path=log_path_value,
    )
