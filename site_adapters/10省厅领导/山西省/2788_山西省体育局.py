from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩列表项排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按省局领导列表顺序解析“职务：姓名”及详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("ul.r_tie li a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.match(r"^·?\s*(?P<duty>.+?)[：:](?P<name>[\u4e00-\u9fff·]{2,8})(?:\s+\d{4}-\d{2}-\d{2})?$", text)
        if match is None or match.group("name") in seen:
            continue
        name, evidence = match.group("name"), clean_text(match.group("duty"))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not evidence or not detail_url:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_sports_duty_name_list_v2",
                     "selector_summary": "leader=ul.r_tie li a[href]；duty=text-before-colon；name=text-after-colon-before-date；detail=href"})
    return rows


PAGE_RULE = {
    "rule_id": "2788", "page_type": "人物列表完整页", "structure_group": "shanxi_sports_duty_name_list", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_sports_duty_name_list_v2",
    "leader_region_selector": "ul.r_tie li a[href]", "name_selector": "text after colon before date", "duty_selector": "text before colon", "detail_link_selector": "ul.r_tie li a[href]",
    "content_scope": {"start_anchor": "省局领导", "end_anchor": "友情链接", "include_selectors": ["ul.r_tie"], "exclude_selectors": []},
  "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "raw_http", "detail_link_selector": "ul.r_tie li a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "列表项含圆点和发布日期，以中文冒号及尾部日期确定姓名职务边界", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "ul.r_tie li a[href]", "name_selector": "text after colon before date", "duty_selector": "text before colon", "detail_link_selector": "ul.r_tie li a[href]", "content_scope": {"start_anchor": "省局领导", "end_anchor": "友情链接", "include_selectors": ["ul.r_tie"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导列表已直出姓名、职务和详情链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
