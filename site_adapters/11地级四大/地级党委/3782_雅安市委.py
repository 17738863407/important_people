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
    "rule_id": "3782",
    "domain": "www.yaan.gov.cn",
    "page_type": "同页市委市政府标签列表",
    "load_mode": "浏览器渲染DOM",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_yaan_party_leaders_v1",
    "leader_region_selector": ".tab-bd .tab-pal",
    "name_selector": ".leader-ul li h1 a",
    "duty_selector": ".leader-ul li p",
    "detail_link_selector": ".leader-ul li h1 a[href]",
    "content_scope": {"start_anchor": "雅安市委领导", "end_anchor": "雅安市政府领导", "include_selectors": [".tab-bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同页含市政府标签，只取首个市委面板",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委面板人物卡片顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    panels = soup.select(".tab-bd > .tab-pal")
    if not panels:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for item in panels[0].select(".leader-ul li"):
        name_link = item.select_one("h1 a[href]")
        duty_node = item.select_one("p")
        if not name_link or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get("title", "") or duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(name_link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
