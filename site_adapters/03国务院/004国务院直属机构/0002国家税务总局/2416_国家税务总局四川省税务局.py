from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2416", "page_type": "人物目录详情页", "structure_group": "sichuan_tax_chrome_leader_sidebar_v3",
    "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "chrome",
    "extract_mode": "list_to_detail", "collector": "chrome_cdp", "parser": "sichuan_tax_chrome_leader_sidebar_v3",
    "leader_region_selector": "领导专栏侧栏 li > a[href]", "name_selector": "领导专栏侧栏链接文本", "duty_selector": ".bottom-text1 p",
    "detail_link_selector": "领导专栏侧栏 li > a[href]", "content_scope": {"start_anchor": "领导专栏", "end_anchor": "机构职能", "include_selectors": [], "exclude_selectors": []},
    "risk_flag": "普通请求412且Playwright仅返回39字节无效页；须使用Chrome CDP并按侧栏顺序逐页提取",
    "confidence": "high", "profile_reusable": "", "profile_judgement": "",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_by_chrome_debug

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.select("li > a[href]"):
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        detail_path = urlparse(detail_url).path
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if not re.fullmatch(r"/col/col204\d+/index\.html", detail_path):
            continue
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise RuntimeError("Chrome渲染页未发现领导专栏人物链接")

    rows: list[dict] = []
    current_path = urlparse(final_url).path
    for name, detail_url in candidates:
        if urlparse(detail_url).path == current_path:
            detail_html = html
            detail_final_url = final_url
        else:
            detail_result = fetch_by_chrome_debug(detail_url, timeout=60)
            detail_html = detail_result.html
            detail_final_url = detail_result.final_url
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        profile = detail_soup.select_one(".bottom-text1 p")
        profile_text = clean_text(profile.get_text(" ", strip=True) if profile else "")
        if name not in profile_text:
            raise RuntimeError(f"人物姓名无法回指详情正文：{detail_final_url}")
        duty_match = re.search(r"国家税务总局四川省税务局[^。]*。", profile_text)
        if duty_match is None:
            raise RuntimeError(f"人物详情页缺少省局职务原文：{detail_final_url}")
        duty = duty_match.group(0)
        detail_export_url = detail_final_url
        if detail_export_url.rstrip("/") == str(page_rule["url"]).strip().rstrip("/"):
            detail_export_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_export_url,
                "parser": page_rule["parser"],
                "selector_summary": "领导专栏侧栏人物链接；详情=.bottom-text1 p",
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
