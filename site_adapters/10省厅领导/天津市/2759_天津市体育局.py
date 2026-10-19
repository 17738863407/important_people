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
    "rule_id": "2759",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_sports_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_sports_leader_cards_v1",
    "leader_region_selector": ".ldxx-right-main",
    "name_selector": "li .ldxx-name",
    "duty_selector": "li .ldxx-zw",
    "detail_link_selector": "li[onclick*='window.open']",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [".ldxx-right-main"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "onclick_links", "detail_collector_type": "static_http", "detail_link_selector": "li[onclick*='window.open']", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "详情链接保存在卡片onclick window.open中；仅解析同时具有姓名和职务强字段的可见li",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".ldxx-right-main li", "name_selector": ".ldxx-name", "duty_selector": ".ldxx-zw", "detail_link_selector": "li[onclick*='window.open']", "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [".ldxx-right-main"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "当前静态HTML领导卡片直接包含姓名、职务和onclick人物链接"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _detail_url(onclick: str, base_url: str) -> str:
    match = re.search(r"window\.open\(\s*['\"]([^'\"]+)['\"]", onclick or "")
    return urljoin(base_url, match.group(1).strip()) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序读取强字段及onclick详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".ldxx-right-main li:has(.ldxx-name):has(.ldxx-zw)"):
        name = re.sub(r"\s+", "", _clean_text(card.select_one(".ldxx-name").get_text(" ", strip=True)))
        duty = _clean_text(card.select_one(".ldxx-zw").get_text(" ", strip=True))
        detail_url = _detail_url(str(card.get("onclick", "")), base_url)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or not detail_url or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                     "parser": "custom_tianjin_sports_leader_cards_v1",
                     "selector_summary": ".ldxx-right-main卡片；.ldxx-name/.ldxx-zw；onclick window.open"})
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
