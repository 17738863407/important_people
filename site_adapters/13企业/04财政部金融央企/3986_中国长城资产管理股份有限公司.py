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
    "rule_id": "3986", "domain": "www.gwamcc.com", "page_type": "公司领导履历列表",
    "structure_group": "gwamcc_governance_leaders", "reuse_scope": "gwamcc_company_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_gwamcc_governance_leaders_v1", "leader_region_selector": "#list_con",
    "name_selector": "#list_con > li .governance_title", "duty_selector": "#list_con > li .governance_listtitle",
    "content_scope": {"include_selectors": ["#list_con"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名可能含排版空格且同卡片含长篇历任履历，只取独立姓名与现职标题字段",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": "#list_con > li", "name_selector": ".governance_title", "duty_selector": ".governance_listtitle"}},
}


def normalize_text(value: str) -> str:
    """清理字段中的普通、全角和不间断空格。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """直接读取每个领导列表项的独立姓名和现职标题。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("#list_con > li"):
        name_node = card.select_one(".governance_title")
        duty_node = card.select_one(".governance_listtitle")
        name = normalize_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = normalize_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "公司领导列表项独立姓名和现职标题",
        })
    if not rows:
        raise RuntimeError("公司领导列表未解析出有效人物")
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
