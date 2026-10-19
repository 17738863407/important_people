from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3603", "domain": "www.hgjjgl.com", "page_type": "职务栏目人物列表",
    "structure_group": "hgjjgl_editorial_director_list_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "heading_duty_person_cards",
    "collector": "static_http", "parser": "page_hgjjgl_editorial_director_v1", "leader_region_selector": ".content .main",
    "name_selector": ".photolist li a[href] span", "duty_selector": ".pgcurr li:last-child",
    "detail_link_selector": ".photolist li a[href]", "detail_strategy": {"required": False, "mode": "direct_person_link", "candidate_links": []},
    "risk_flag": "duty_from_current_column_heading", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅从当前“编委会主任”入口页提取人物，不扩展到编委栏目。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content .main")
    if region is None: return []
    def extract_cards(content: BeautifulSoup, page_url: str, duty: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for link in content.select(".photolist li a[href]"):
            name_node = link.select_one("span")
            name = clean(name_node.get_text(" ", strip=True) if name_node else "")
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                rows.append({"name": name, "duty": duty, "evidence": duty,
                             "detail_url": urljoin(page_url, str(link.get("href", ""))), "parser": str(page_rule.get("parser", "")),
                             "selector_summary": "strategy=custom_parse_page；region=.content .main；duty=.pgcurr li:last-child；person=.photolist li a span"})
        return rows

    duty_node = region.select_one(".pgcurr li:last-child")
    duty = clean(duty_node.get_text(" ", strip=True) if duty_node else "")
    return extract_cards(region, final_url, duty)


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
