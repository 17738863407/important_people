from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2563",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_leader_sidebar_to_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom_parse_page",
    "collector": "chrome_cdp",
    "parser": "page_inline_nanchang_leader_sidebar_detail_v1",
    "leader_region_selector": ".leader-menus ul.ul2",
    "name_selector": "> li > a[title][href]",
    "duty_selector": "dl.leader-info dd .leader-text.mb:first-of-type",
    "detail_link_selector": "> li > a[title][href]",
    "detail_strategy": {"required": True, "mode": "sidebar_to_detail", "max_detail_links": 20},
    "risk_flag": "站点对普通HTTP及无头浏览器返回403；当前仅Chrome CDP可取得真实页面",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """只清理网页排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def normalize_url_identity(value: str) -> tuple[str, str, str]:
    """归一化URL身份，忽略协议、片段、默认端口和路径末尾斜杠差异。"""
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port not in {None, 80, 443}:
        hostname = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    return hostname, path, parsed.query


def fetch_detail(detail_url: str, expected_name: str) -> str:
    """通过已核验可用的Chrome CDP取得详情页并读取强结构职务字段。"""
    from crawler_core.fetcher import fetch_by_chrome_debug

    result = fetch_by_chrome_debug(detail_url, timeout=40)
    soup = BeautifulSoup(result.html or "", "html.parser")
    region = soup.select_one("dl.leader-info")
    if region is None:
        return ""
    name_node = region.select_one("dt h4")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
    if name != expected_name:
        return ""
    duty_node = region.select_one("dd .leader-text.mb")
    return clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏人物链接顺序逐页核验姓名并读取详情职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    entry_url = str(page_rule.get("url") or "") or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select(":scope > li > a[title][href]"):
        name = clean_text(link.get("title") or link.get_text(" ", strip=True)).replace(" ", "")
        href = clean_text(link.get("href"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or entry_url, href)
        evidence = ""
        for _ in range(2):
            try:
                evidence = fetch_detail(detail_url, name)
            except Exception:
                evidence = ""
            if evidence:
                break
        seen.add(name)
        verified_detail_url = ""
        if evidence and normalize_url_identity(detail_url) != normalize_url_identity(entry_url):
            verified_detail_url = detail_url
        records.append(
            {
                "organization": str(page_rule.get("organization") or ""),
                "url": entry_url,
                "name": name,
                "duty": evidence,
                "detail_url": verified_detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": (
                    "sidebar=.leader-menus ul.ul2 > li > a[title][href]；"
                    "detail=dl.leader-info；name=dt h4；duty=dd .leader-text.mb:first"
                ),
            }
        )
    return records


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
