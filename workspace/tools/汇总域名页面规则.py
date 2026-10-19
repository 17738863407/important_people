from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import runpy
from typing import Any

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台和日志文件。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def iter_adapter_scripts(adapter_dir: Path) -> list[Path]:
    """递归获取页面级爬虫脚本。"""
    if not adapter_dir.exists():
        return []
    return sorted(
        path
        for path in adapter_dir.rglob("*.py")
        if path.is_file() and not path.name.startswith("_")
    )


def load_page_rule(script_path: Path) -> dict[str, Any]:
    """从脚本中读取 PAGE_RULE，不触发脚本 main()。"""
    namespace = runpy.run_path(str(script_path))
    page_rule = namespace.get("PAGE_RULE")
    if not isinstance(page_rule, dict):
        raise ValueError("脚本缺少 PAGE_RULE 字典")
    return page_rule


def text_value(rule: dict[str, Any], key: str) -> str:
    """读取规则字段并转为文本。"""
    return str(rule.get(key, "") or "").strip()


def safe_cell(value: object) -> str:
    """清理制表符和换行，避免破坏 TXT 表格结构。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def build_signature(rule: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    """生成可复用页面规则签名。"""
    return (
        text_value(rule, "domain"),
        text_value(rule, "page_type"),
        text_value(rule, "load_mode"),
        text_value(rule, "parser"),
        text_value(rule, "leader_region_selector"),
        text_value(rule, "detail_link_selector"),
    )


def main(adapter_dir: Path, output_path: Path, log_path: Path, min_reuse_count: int) -> None:
    """汇总域名页面规则，形成可复用模板候选清单。"""
    if log_path.exists():
        log_path.unlink()
    scripts = iter_adapter_scripts(adapter_dir)
    write_log(log_path, f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_log(log_path, f"脚本目录：{adapter_dir}")
    write_log(log_path, f"脚本数量：{len(scripts)}")

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    grouped_rules: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    failed_rows: list[tuple[str, str]] = []
    iterator = tqdm(scripts, desc="汇总页面规则") if tqdm else scripts
    for script_path in iterator:
        try:
            rule = load_page_rule(script_path)
            grouped_rules[build_signature(rule)].append(
                {
                    "script": str(script_path),
                    "organization": text_value(rule, "organization"),
                    "url": text_value(rule, "url"),
                }
            )
        except Exception as error:
            failed_rows.append((script_path.name, str(error)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "复用等级",
        "复用数量",
        "域名",
        "页面类型",
        "加载方式",
        "解析器",
        "领导区域选择器",
        "详情页选择器",
        "示例机构",
        "示例网址",
        "示例脚本",
    ]
    rows: list[list[str]] = []
    for signature, examples in grouped_rules.items():
        if len(examples) < min_reuse_count:
            continue
        domain, page_type, load_mode, parser, leader_selector, detail_selector = signature
        reuse_level = "高" if len(examples) >= 10 else "中"
        sample_examples = examples[:5]
        rows.append(
            [
                reuse_level,
                str(len(examples)),
                domain,
                page_type,
                load_mode,
                parser,
                leader_selector,
                detail_selector,
                "；".join(item["organization"] for item in sample_examples),
                "；".join(item["url"] for item in sample_examples),
                "；".join(item["script"] for item in sample_examples),
            ]
        )
    rows.sort(key=lambda row: (0 if row[0] == "高" else 1, -int(row[1]), row[2], row[3]))

    with output_path.open("w", encoding="utf-8") as file:
        file.write("\t".join(fields) + "\n")
        for row in rows:
            file.write("\t".join(safe_cell(value) for value in row) + "\n")
        if failed_rows:
            file.write("\n读取失败脚本\t失败原因\n")
            for script_name, reason in failed_rows:
                file.write(f"{safe_cell(script_name)}\t{safe_cell(reason)}\n")

    write_log(log_path, f"可复用规则组数：{len(rows)}")
    write_log(log_path, f"读取失败脚本数：{len(failed_rows)}")
    write_log(log_path, f"结果文件：{output_path}")
    write_log(log_path, f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    adapter_dir_value = resolve_project_path("important_people/site_adapters", anchor=__file__)
    output_path_value = resolve_project_path(
        "important_people/workspace/reports/域名页面规则复用建议.txt", anchor=__file__
    )
    log_path_value = resolve_project_path(
        "important_people/workspace/log/汇总域名页面规则.log", anchor=__file__
    )
    min_reuse_count_value = 2
    main(
        adapter_dir=adapter_dir_value,
        output_path=output_path_value,
        log_path=log_path_value,
        min_reuse_count=min_reuse_count_value,
    )
