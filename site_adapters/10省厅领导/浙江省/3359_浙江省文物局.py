from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3359",
    "page_type": "人物列表完整页",
    "structure_group": "zhejiang_department_leader_cards_first_duty_paragraph",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_zhejiang_cultural_relics_leader_cards_v2",
    "leader_region_selector": ".ld[data-showlist='2']",
    "name_selector": ".ld_tit",
    "duty_selector": ".jg_ldxx_item.ldzw .txt_item内首个非空p",
    "detail_link_selector": ".ld[data-showlist='2'] > a[href]",
    "content_scope": {"start_anchor": "首张领导卡", "end_anchor": "末张领导卡", "include_selectors": [".ld[data-showlist='2'] > a[href]"], "exclude_selectors": ["ldzw后续职责段", "职责分工", "文物业务", "页脚"]},
    "detail_strategy": {"required": False, "mode": "dynamic_link_from_card", "detail_collector_type": "raw_http", "detail_link_selector": ".ld[data-showlist='2'] > a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "首卡ldzw含职务段和主持职责段；仅取首个非空p为职务，其余职责排除",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".ld[data-showlist='2']", "name_selector": ".ld_tit", "duty_selector": ".jg_ldxx_item.ldzw .txt_item > p:first-of-type", "detail_link_selector": ".ld[data-showlist='2'] > a[href]", "content_scope": {"start_anchor": "首张领导卡", "end_anchor": "末张领导卡", "include_selectors": [".ld[data-showlist='2'] > a[href]"], "exclude_selectors": ["ldzw后续职责段", "职责分工", "文物业务", "页脚"]}}, "api": {"enabled": False, "reason": "静态HTML卡片直接提供姓名、职务段与详情链接"}},
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true" or "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if current.name == "div" and "ld" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _first_duty_paragraph(node: Tag | None) -> str:
    if node is None:
        return ""
    paragraphs = [_clean_text(item.get_text(" ", strip=True)) for item in node.select("p")]
    return next((text for text in paragraphs if text), _clean_text(node.get_text(" ", strip=True)))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".ld[data-showlist='2'] > a[href]"):
        if _is_hidden(link):
            continue
        name_node = link.select_one(".ld_tit")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = _first_duty_paragraph(link.select_one(".jg_ldxx_item.ldzw .txt_item"))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not duty or not href or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, href), "evidence": duty, "parser": "custom_zhejiang_cultural_relics_leader_cards_v2", "selector_summary": "同卡.ld_tit与.ldzw首个非空p；外层a详情"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
