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


PAGE_RULE = {
    "rule_id": "0612",
    "page_type": "人物目录详情页",
    "structure_group": "kunming_police_detail_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_police_detail_current_sentence_v2",
    "leader_region_selector": ".right.fr .leadership-list-data",
    "name_selector": ".leadership-list-data a[href] p",
    "duty_selector": ".right.fr",
    "detail_link_selector": ".leadership-list-data a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_link_selector": ".leadership-list-data a[href]",
        "detail_content_selector": ".right.fr",
        "max_detail_links": 50,
    },
    "risk_flag": "详情正文另含简历和分工，只接受当前人物详情区域内完整“现任……”句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def extract_current_sentence(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right.fr") or soup.select_one(".right")
    text = clean_text(region.get_text(" ", strip=True) if region else "")
    match = re.search(r"现任[^。]*。", text)
    return re.sub(r"^现任\s*", "", clean_text(match.group(0))).rstrip("。 ") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序抓取详情页，并提取完整现任职务原句。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_online_html

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".right.fr .leadership-list-data a[href]"):
        name_node = link.select_one("p")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        if not name or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        detail_html, fetched_url = fetch_online_html(detail_url)
        evidence = extract_current_sentence(detail_html)
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": fetched_url or detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": page_rule["parser"],
            }
        )
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
