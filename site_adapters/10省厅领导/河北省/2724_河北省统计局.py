from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2724",
    "page_type": "职务分组名单页",
    "structure_group": "hebei_statistics_numbered_duty_name_lines",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_statistics_numbered_duty_name_lines_v1",
    "leader_region_selector": ".p-jj-body #BodyLabel",
    "name_selector": "p中文冒号后字段",
    "duty_selector": "p中文冒号前去序号字段",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "", "include_selectors": [".p-jj-body #BodyLabel"], "exclude_selectors": ["#aiAssistRoot"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "正文以编号+职务：姓名列出；严格限制单个中文姓名，排除空段落",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".p-jj-body #BodyLabel", "name_selector": "p中文冒号后字段", "duty_selector": "p中文冒号前去序号字段", "detail_link_selector": "", "content_scope": {"start_anchor": "领导介绍", "end_anchor": "", "include_selectors": [".p-jj-body #BodyLabel"], "exclude_selectors": ["#aiAssistRoot"]}}, "api": {"enabled": False, "reason": "静态HTML正文直接含编号职务与姓名"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析“编号.职务：姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".p-jj-body #BodyLabel")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select(":scope > p") if scope else []:
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text:
            continue
        duty_raw, name_raw = text.split("：", 1)
        duty = re.sub(r"^\s*\d+\s*[.．、]?\s*", "", duty_raw).strip()
        name = re.sub(r"\s+", "", name_raw)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_statistics_numbered_duty_name_lines_v1", "selector_summary": ".p-jj-body #BodyLabel直接p；编号.职务：姓名"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
