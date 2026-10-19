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
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按职务分组及分组内姓名链接顺序抽取领导。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in soup.select("ul.provincial-leaders-inner > li"):
        duty_node = group.select_one(".provincial-leaders-position")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not evidence:
            continue
        for link in group.select("dd a[href]"):
            name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
            detail_url = urljoin(final_url, str(link.get("href") or ""))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_url or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                         "confidence": "high", "parser": "page_inline_shanxi_forestry_grouped_cards_v2",
                         "selector_summary": "group=ul.provincial-leaders-inner>li；duty=.provincial-leaders-position；name/detail=dd a[href]"})
    return rows


PAGE_RULE = {
    "rule_id": "1419", "page_type": "人物列表完整页", "structure_group": "shanxi_forestry_grouped_leader_cards", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom_parse_page", "collector": "static_http", "parser": "page_inline_shanxi_forestry_grouped_cards_v3",
    "leader_region_selector": "ul.provincial-leaders-inner > li", "name_selector": "dd a[href]", "duty_selector": ".provincial-leaders-position", "detail_link_selector": "dd a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul.provincial-leaders-inner"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "online", "detail_link_selector": "dd a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "增强HTTP会跟随页面空搜索脚本导致404，须用raw_http保留当前响应；图片锚点与姓名锚点重复，忽略空文本链接", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "ul.provincial-leaders-inner > li", "name_selector": "dd a[href]", "duty_selector": ".provincial-leaders-position", "detail_link_selector": "dd a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul.provincial-leaders-inner"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "浏览器DOM职务分组已直出姓名、职务和个人页链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
