from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2521",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_sport_sidebar_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_sport_sidebar_leader_links_v1",
    "leader_region_selector": "#my-sticky ul.amz-top",
    "name_selector": "li > a文本首字段",
    "duty_selector": "li > a文本姓名后字段",
    "detail_link_selector": "li > a[href]",
    "content_scope": {"start_anchor": "省局领导", "end_anchor": "", "include_selectors": ["#my-sticky ul.amz-top"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "person_name_link", "detail_collector_type": "static_http", "detail_link_selector": "li > a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "页面其他位置存在同路径栏目及当前人物重复链接；仅使用省局领导侧栏列表",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#my-sticky ul.amz-top", "name_selector": "li > a文本首字段", "duty_selector": "li > a文本姓名后字段", "detail_link_selector": "li > a[href]", "content_scope": {"start_anchor": "省局领导", "end_anchor": "", "include_selectors": ["#my-sticky ul.amz-top"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML省局领导侧栏直接含姓名、职务和详情链接"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split()).lstrip(">").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按省局领导侧栏原始顺序提取人物和独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#my-sticky ul.amz-top")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in scope.select(":scope > li > a[href]") if scope else []:
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)$", text)
        if not match or match.group("name") in seen:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        detail_url = urljoin(final_url, link.get("href", ""))
        if detail_url.rstrip("/") == str(page_rule.get("url", "")).rstrip("/"):
            detail_url = ""
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": "custom_hebei_sport_sidebar_leader_links_v1", "selector_summary": "#my-sticky ul.amz-top直接li链接；姓名 职务"})
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
