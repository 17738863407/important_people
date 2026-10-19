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
    "rule_id": "1697",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_mpa_leader_navigation_profiles",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_jilin_mpa_leader_navigation_profiles_v2",
    "leader_region_selector": ".laderLeft",
    "name_selector": ".laderLeft > a[href]",
    "duty_selector": ".laderTxt > .zhiwu",
    "detail_link_selector": ".laderTxt > a[href]",
    "detail_strategy": {"required": False, "mode": "navigation_to_profile_pages"},
    "risk_flag": "入口正文只显示当前领导，必须按左侧领导简介导航顺序逐页提取",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    navigation = soup.select_one(".laderLeft")
    if not navigation:
        return []

    rows: list[dict[str, str]] = []
    seen_pages: set[str] = set()
    for link in navigation.select(":scope > a[href]"):
        profile_url = urljoin(final_url, str(link.get("href") or ""))
        if not profile_url or profile_url in seen_pages:
            continue
        seen_pages.add(profile_url)

        if profile_url.rstrip("/") == final_url.rstrip("/"):
            profile_soup = soup
            profile_final_url = final_url
        else:
            fetched = fetch_by_raw_requests(profile_url)
            profile_soup = BeautifulSoup(fetched.html, "html.parser")
            profile_final_url = fetched.final_url

        root = profile_soup.select_one(".laderTxt")
        if not root:
            continue
        name_node = root.select_one(":scope > .peopleName")
        duty_nodes = root.select(":scope > .zhiwu")
        detail_node = root.select_one(":scope > a[href]")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = next(
            (clean_text(node.get_text(" ", strip=True)) for node in duty_nodes if clean_text(node.get_text(" ", strip=True))),
            "",
        )
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        detail_url = urljoin(profile_final_url, str(detail_node.get("href") or "")) if detail_node else ""
        if detail_url.rstrip("/") in {
            str(rule.get("url") or "").strip().rstrip("/"),
            profile_final_url.rstrip("/"),
        }:
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_jilin_mpa_leader_navigation_profiles_v2",
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
