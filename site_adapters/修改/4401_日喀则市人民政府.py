from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


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


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从当前导航动态发现领导目录，按列表原序读取各人简介的完整现任句。"""
    import re
    from bs4 import BeautifulSoup

    current_url = _with_www(final_url)
    soup = BeautifulSoup(_request_text(current_url), "html.parser")
    region = soup.select_one(".goverment-leaders .leader-lists")
    if region is None:
        link = next((a for a in soup.select("a[href]") if a.get_text(" ", strip=True) == "领导之窗"), None)
        if link is None:
            raise RuntimeError("当前政府入口未发现领导之窗")
        candidate = urljoin(current_url, str(link["href"]))
        if urlsplit(candidate).netloc.lower() != urlsplit(current_url).netloc.lower():
            raise RuntimeError("领导之窗链接超出当前官网主机")
        current_url = candidate
        soup = BeautifulSoup(_request_text(current_url), "html.parser")
        region = soup.select_one(".goverment-leaders .leader-lists")
    if region is None:
        raise RuntimeError("未取得当前市政府领导目录")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in region.find_all("div", class_="item", recursive=False):
        for link in group.select("ul > li > a[href]"):
            if any(n.has_attr("hidden") or n.get("aria-hidden") == "true" or "display:none" in str(n.get("style", "")).replace(" ", "") for n in [link, *link.parents]):
                continue
            name = "".join(link.get_text(" ", strip=True).split())
            if not name or name in seen:
                raise RuntimeError("当前领导目录姓名缺失或重复")
            detail_url = urljoin(current_url, str(link["href"]))
            detail_soup = BeautifulSoup(_request_text(detail_url), "html.parser")
            intro_node = detail_soup.select_one(".leader-info-box .leader-resume .intro")
            intro = "".join(intro_node.get_text(" ", strip=True).split()) if intro_node else ""
            if not intro.startswith(name):
                raise RuntimeError(f"人物简介与当前目录姓名不符：{name}")
            current = re.search(r"现任([^。]+)(?:。|$)", intro)
            if current is None:
                raise RuntimeError(f"当前人物简介缺少明确现职句：{name}")
            evidence = current.group(1)
            seen.add(name)
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url})
    if not rows:
        raise RuntimeError("当前领导目录未取得明确人物")
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
