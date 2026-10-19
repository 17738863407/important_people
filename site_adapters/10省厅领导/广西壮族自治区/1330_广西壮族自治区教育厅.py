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



def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


PAGE_RULE = {
    "rule_id": "1330",
    "domain": "jyt.gxzf.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "guangxi_education_overview_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_guangxi_education_overview_leader_links_v1",
    "leader_region_selector": "a[href*='ldjl/t']",
    "detail_link_selector": "a[href*='ldjl/t']",
    "content_scope": {
        "include_selectors": ["a[href*='ldjl/t']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_link_selector": "a[href*='ldjl/t']",
        "max_detail_links": 50,
    },
    "risk_flag": "fixed_live_overview_links_no_detail_chain",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def extract_from_link_text(text: str) -> tuple[str, str] | None:
    value = normalize_space(text)
    match = re.match(r"^(.{2,8})[:：]\s*(.+)$", value)
    if not match:
        return None
    name = clean_name(match.group(1))
    duty = normalize_space(match.group(2))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    return name, duty


def collect_links(soup: BeautifulSoup, selector: str) -> list[BeautifulSoup]:
    return soup.select(selector)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    selector = str(page_rule.get("leader_region_selector", "")).strip()
    if not selector:
        return []

    for link in collect_links(soup, selector):
        result = extract_from_link_text(link.get_text(" ", strip=True))
        if not result:
            continue
        name, duty = result
        if name in seen:
            continue
        seen.add(name)
        href = str(link.get("href", "")).strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(base_url, href)
            if candidate_url.rstrip("/") != base_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；source=机构概况页领导简介链接；field=链接文本姓名:职务",
            }
        )

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
