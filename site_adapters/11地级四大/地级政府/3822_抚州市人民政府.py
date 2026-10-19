from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def normalize_url(value: str) -> str:
    """规范化网页地址，用于识别仅尾部斜杠或片段不同的同址链接。"""
    parsed = urlsplit(str(value or "").strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def detail_url_or_blank(candidate: str, entry_url: str) -> str:
    """入口页本身不是独立人物详情页，同址时必须留空。"""
    return "" if normalize_url(candidate) == normalize_url(entry_url) else candidate


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从当前领导详情页的市政府领导分组名单提取全部人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".main01_r01 .ldl")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    entry_url = str(page_rule.get("url", "")) or source_url
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > li"):
        direct_divs = group.find_all("div", recursive=False)
        duty = clean_text(direct_divs[0].get_text(" ", strip=True)).replace(" ", "") if direct_divs else ""
        if not duty:
            continue
        for link in group.select("a.a20[href]"):
            name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            candidate_url = urljoin(source_url, str(link.get("href") or ""))
            detail_url = detail_url_or_blank(candidate_url, entry_url)
            rows.append({"name": name, "duty": "", "evidence": duty, "detail_url": detail_url,
                         "confidence": "high", "parser": "page_inline_fuzhou_government_sidebar_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3822",
    "page_type": "详情页内领导分组名单",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "_fetch_mode_override": True,
    "extract_mode": "list_direct",
    "parser": "page_inline_fuzhou_government_sidebar_v1",
    "leader_region_selector": ".main01_r01 .ldl",
    "name_selector": "a.a20",
    "duty_selector": "li > div:first-child",
    "detail_link_selector": "a.a20[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "HTTP直连返回503关闭响应，需浏览器渲染",
    "confidence": "high",
}


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
