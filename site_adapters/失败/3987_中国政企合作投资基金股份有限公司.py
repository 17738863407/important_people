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
    "rule_id": "3987", "domain": "www.cpppf.org", "page_type": "双机构经营管理层选项卡",
    "structure_group": "cpppf_dual_entity_management", "reuse_scope": "cpppf_corporate_governance",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_cpppf_target_entity_management_v2", "leader_region_selector": "#title-list, #con-box",
    "name_selector": "#con-box > .dir_tab_page_con dl > dt", "duty_selector": "#con-box > .dir_tab_page_con dl > dd",
    "content_scope": {"include_selectors": ["#title-list", "#con-box"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页并列两家机构的经营管理层，必须根据运行器注入的机构名称定位同序面板",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"entity_tabs": "#title-list > li", "entity_panels": "#con-box > .dir_tab_page_con", "record_selector": "dl"}},
}


def normalize_text(value: str) -> str:
    """清理字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按运行器注入的机构名称定位同序经营管理层面板。"""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#title-list") or not soup.select_one("#con-box"):
        from crawler_core.fetcher import fetch_html_with_strategy

        raw_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="raw_http")
        soup = BeautifulSoup(raw_result.html, "html.parser")
    entity_nodes = soup.select("#title-list > li")
    entity_titles = [normalize_text(node.get_text(" ", strip=True)) for node in entity_nodes]
    panels = soup.select("#con-box > .dir_tab_page_con")
    target_organization = normalize_text(str(page_rule.get("organization", "")))
    if not target_organization or not entity_titles or not panels:
        raise RuntimeError("未确认机构标题与经营管理层面板")
    try:
        target_index = entity_titles.index(target_organization)
    except ValueError as error:
        raise RuntimeError("页面机构标题未找到规则主表注入的目标机构") from error
    if target_index >= len(panels):
        raise RuntimeError("目标机构标题未找到同序经营管理层面板")
    rows: list[dict[str, str]] = []
    for item in panels[target_index].select("dl"):
        name_node = item.select_one(":scope > dt")
        duty_node = item.select_one(":scope > dd")
        name = normalize_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = normalize_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "目标机构标题同序经营管理层面板dl姓名职务",
        })
    if not rows:
        raise RuntimeError("股份公司经营管理层未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
