from __future__ import annotations

import runpy
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

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
    """获取平铺页面级爬虫脚本。"""
    if not adapter_dir.exists():
        return []
    return sorted(
        path
        for path in adapter_dir.glob("*.py")
        if path.is_file() and not path.name.startswith("_")
    )


def load_page_rule(script_path: Path) -> dict:
    """读取脚本中的 PAGE_RULE。"""
    namespace = runpy.run_path(str(script_path))
    page_rule = namespace.get("PAGE_RULE")
    if not isinstance(page_rule, dict):
        raise ValueError("脚本缺少 PAGE_RULE 字典")
    return page_rule


def selector_is_explicit(selector: str) -> bool:
    """判断选择器是否为明确 CSS 选择器。"""
    text = str(selector or "").strip()
    if not text:
        return False
    invalid_hints = ["角色关键词", "fallback", "语义识别", "同一行", "相邻", "冒号后", "冒号前"]
    return not any(hint in text for hint in invalid_hints)


def count_selector_matches(html: str, selector: str) -> tuple[int, str]:
    """统计 CSS 选择器命中数量。"""
    if not selector_is_explicit(selector):
        return 0, "选择器为空或不是明确 CSS"
    soup = BeautifulSoup(html, "html.parser")
    try:
        nodes = soup.select(selector)
    except Exception as error:
        return 0, f"选择器执行失败：{error}"
    return len(nodes), ""


def inspect_one_script(script_path: Path, timeout_seconds: int) -> dict[str, str]:
    """在线检查单个脚本的主要选择器。"""
    from crawler_core.fetcher import fetch_online_html_with_fallback

    page_rule = load_page_rule(script_path)
    fetch_result = fetch_online_html_with_fallback(str(page_rule["url"]), timeout=timeout_seconds)
    html = fetch_result.html
    result: dict[str, str] = {
        "脚本": script_path.name,
        "机构": str(page_rule.get("organization", "")),
        "网址": str(page_rule.get("url", "")),
        "采集器": fetch_result.collector,
        "HTTP状态码": str(fetch_result.status_code or ""),
        "内容类型": fetch_result.content_type,
        "采集警告": "；".join(fetch_result.warnings),
    }
    for field_name in ["leader_region_selector", "detail_link_selector"]:
        selector = str(page_rule.get(field_name, ""))
        count, error = count_selector_matches(html, selector)
        result[field_name] = selector
        result[f"{field_name}_命中数"] = str(count)
        result[f"{field_name}_问题"] = error
    return result


def main(adapter_dir: Path, output_path: Path, log_path: Path, timeout_seconds: int) -> None:
    """批量检查页面级爬虫脚本选择器。"""
    scripts = iter_adapter_scripts(adapter_dir)
    if log_path.exists():
        log_path.unlink()
    write_log(log_path, f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_log(log_path, f"检查脚本数量：{len(scripts)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "脚本",
        "机构",
        "网址",
        "采集器",
        "HTTP状态码",
        "内容类型",
        "采集警告",
        "leader_region_selector",
        "leader_region_selector_命中数",
        "leader_region_selector_问题",
        "detail_link_selector",
        "detail_link_selector_命中数",
        "detail_link_selector_问题",
    ]
    with output_path.open("w", encoding="utf-8") as file:
        file.write("\t".join(fields) + "\n")
        for index, script_path in enumerate(scripts, start=1):
            write_log(log_path, f"[{index}/{len(scripts)}] 检查：{script_path.name}")
            try:
                row = inspect_one_script(script_path, timeout_seconds)
            except Exception as error:
                row = {"脚本": script_path.name, "机构": "", "网址": "", "采集器": "", "leader_region_selector_问题": str(error)}
            file.write("\t".join(str(row.get(field, "")).replace("\t", " ") for field in fields) + "\n")
    write_log(log_path, f"结果文件：{output_path}")


if __name__ == "__main__":
    adapter_dir_value = resolve_project_path("important_people/site_adapters", anchor=__file__)
    output_path_value = resolve_project_path(
        "important_people/workspace/reports/爬虫脚本选择器检查结果.txt", anchor=__file__
    )
    log_path_value = resolve_project_path(
        "important_people/workspace/log/检查爬虫脚本选择器.log", anchor=__file__
    )
    timeout_seconds_value = 30
    main(
        adapter_dir=adapter_dir_value,
        output_path=output_path_value,
        log_path=log_path_value,
        timeout_seconds=timeout_seconds_value,
    )
