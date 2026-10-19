from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2703",
    "page_type": "人物目录详情页",
    "structure_group": "anhui_sports_browser_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "parse_page",
    "leader_region_selector": "#zdgkList > ul.xxgk_nav_list > li",
    "name_selector": "a.title[href*='/public/21751/']",
    "duty_selector": "详情页 #wenzhang .wzcon.j-fontContent 中的现任句",
    "detail_link_selector": "a.title[href*='/public/21751/']",
    "content_scope": {
        "start_anchor": "机构领导",
        "end_anchor": "友情链接",
        "include_selectors": ["#zdgkList"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "person_name_link",
        "detail_collector_type": "playwright",
        "detail_link_selector": "a.title[href*='/public/21751/']",
        "detail_name_selector": "#wenzhang h1.newstitle",
        "detail_duty_selector": "#wenzhang .wzcon.j-fontContent",
        "detail_content_selector": "#wenzhang .wzcon.j-fontContent",
        "max_detail_links": 20,
    },
    "risk_flag": "普通HTTP被CloudWAF拦截；详情职责段紧随现任职务句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _clean_name(value: str) -> str:
    """清理并校验目录或详情页姓名。"""
    name = re.sub(r"\s+", "", value)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序，用浏览器逐页核对姓名并提取完整现任职务句。"""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("#zdgkList > ul.xxgk_nav_list > li")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for item in items:
        link = item.select_one("a.title[href*='/public/21751/']")
        if link is None:
            continue
        name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if (
            not name
            or urlparse(detail_url).netloc != urlparse(final_url).netloc
            or not re.fullmatch(r"/public/21751/\d+\.html", urlparse(detail_url).path)
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise RuntimeError("渲染目录未解析出有效人物详情链接")

    from crawler_core.fetcher import fetch_by_playwright_subprocess

    rows: list[dict[str, str]] = []
    for expected_name, detail_url in candidates:
        result = fetch_by_playwright_subprocess(detail_url, timeout=60)
        detail_soup = BeautifulSoup(result.html, "html.parser")
        title_node = detail_soup.select_one("#wenzhang h1.newstitle")
        actual_name = _clean_name(title_node.get_text(" ", strip=True) if title_node else "")
        if actual_name != expected_name:
            raise RuntimeError(f"详情页姓名与目录不一致：{expected_name} -> {actual_name}")
        content_node = detail_soup.select_one("#wenzhang .wzcon.j-fontContent")
        content = _clean_text(content_node.get_text(" ", strip=True) if content_node else "")
        duty_match = re.search(r"现任[^。]*。", content)
        if duty_match is None:
            raise RuntimeError(f"详情页未找到现任职务句：{expected_name}")
        evidence = re.sub(r"^现任\s*", "", re.sub(r"\s+", "", duty_match.group(0))).rstrip("。")
        rows.append(
            {
                "name": expected_name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=playwright_subprocess+css；"
                    "directory=#zdgkList > ul.xxgk_nav_list > li a.title；"
                    "detail_name=#wenzhang h1.newstitle；"
                    "detail_content=#wenzhang .wzcon.j-fontContent；evidence=当前人物现任句"
                ),
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
