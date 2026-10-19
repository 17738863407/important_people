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
    "rule_id": "3982", "domain": "www.sinosure.com.cn", "page_type": "公司领导卡片列表",
    "structure_group": "sinosure_leader_cards", "reuse_scope": "sinosure_company_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_sinosure_leader_cards_v1", "leader_region_selector": ".major .leader",
    "name_selector": ".leader-lead .lead-left p > span:first-child", "duty_selector": ".leader-lead .lead-left p",
    "content_scope": {"include_selectors": [".major .leader"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务位于同一段落，须按首个span边界拆分且不把头像链接视为详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": ".major .leader .leader-lead", "name_selector": ".lead-left p > span:first-child"}},
}


def normalize_text(value: str) -> str:
    """清理全角空格及排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片段落首个姓名span拆分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".major .leader .leader-lead"):
        paragraph = card.select_one(".lead-left p")
        name_node = paragraph.select_one(":scope > span:first-child") if paragraph else None
        if paragraph is None or name_node is None:
            continue
        name = normalize_text(name_node.get_text(" ", strip=True))
        full_text = normalize_text(paragraph.get_text(" ", strip=True))
        duty = full_text[len(name):] if full_text.startswith(name) else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "公司领导卡片段落首个span姓名及其后职务",
        })
    if not rows:
        raise RuntimeError("公司领导卡片未解析出有效人物")
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
