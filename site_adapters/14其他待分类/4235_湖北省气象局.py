from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4235", "page_type": "领导卡片页", "load_mode": "静态 HTML 直出",
    "extract_mode": "card_list", "parser": "page_inline_hb_cma_leaders_v1",
    "leader_region_selector": ".sidebar-leader", "name_selector": ".sidebar-leader .name",
    "duty_selector": ".sidebar-leader .job", "detail_link_selector": ".sidebar-leader li > a[href]",
    "detail_strategy": {"required": False, "mode": "person_profile_link"}, "confidence": "high", "filter_policy": "strong_card_structure",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """仅解析桌面端“领导主站”卡片，避免移动端重复展示。"""
    from bs4 import BeautifulSoup
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        str(page_rule["url"]),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=30,
        verify=False,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    rows: list[dict] = []
    for card in BeautifulSoup(response.text, "html.parser").select(".sidebar-leader > ul.list > li"):
        link = card.select_one("a[href]")
        name_node = card.select_one(".name")
        duty_node = card.select_one(".job")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        detail_url = urljoin(final_url, link.get("href")) if link and link.get("href") else ""
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url})
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
