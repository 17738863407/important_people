from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4401",
    "page_type": "government_leader_cards_host_alias",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "risk": "规则主表裸域名当前无DNS记录；已实时核验同路径www主机为官网页面，内置解析器仅作同域主机规范化。",
    "confidence": "high",
}


def _with_www(url: str) -> str:
    """将官网当前失效的裸域名替换为已验证的www同域主机。"""
    parts = urlsplit(url)
    host = parts.netloc
    if host == "rikaze.gov.cn":
        host = "www.rikaze.gov.cn"
    return urlunsplit((parts.scheme or "http", host, parts.path, parts.query, parts.fragment))


def _request_text(url: str) -> str:
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(_with_www(url), headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """从已验证www同路径页面提取市政府领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_request_text(final_url), "html.parser")
    region = soup.select_one(".left-leaders-list .others")
    if region is None:
        return []
    title = region.select_one(".title h4")
    if title is None or title.get_text(" ", strip=True) != "市政府领导":
        return []
    rows: list[dict[str, str]] = []
    for link in region.select("ul > li > a[href]"):
        name_node = link.select_one("h6")
        duty_node = link.select_one("p")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if name and duty:
            rows.append({"name": name, "duty": duty, "detail_url": _with_www(link["href"])})
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
