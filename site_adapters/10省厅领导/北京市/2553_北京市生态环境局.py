from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2553",
    "domain": "sthjj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_ecology_paged_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "paged_list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_ecology_paged_leader_cards_v1",
    "risk_flag": "领导列表分为多页；必须从分页控件动态发现后续页并按页序合并",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_rows(html: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按单页人物卡片DOM顺序解析姓名和原始职务句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".h_ld_m .h_ld_c"):
        evidence = clean_text(card.select_one(".h_ld_r").get_text(" ", strip=True) if card.select_one(".h_ld_r") else "")
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})，(?P<duty>[^。]+)。", evidence)
        if match is None:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "duty": clean_text(match.group("duty")),
                "detail_url": "",
                "evidence": clean_text(match.group("duty")),
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".h_ld_m内h_ld_c人物卡片",
            }
        )
    return rows


def discover_page_urls(html: str, final_url: str) -> list[str]:
    """从分页控件的查询函数参数中动态取得后续页面地址。"""
    soup = BeautifulSoup(html, "html.parser")
    page_urls: list[str] = []
    for anchor in soup.select(".h_ld_m .l_m_bd a[onclick]"):
        match = re.search(r"queryArticleByCondition\([^,]+,\s*['\"](?P<path>[^'\"]+)['\"]", anchor.get("onclick", ""))
        if match is None:
            continue
        page_url = urljoin(final_url, match.group("path"))
        if page_url != final_url and page_url not in page_urls:
            page_urls.append(page_url)
    return page_urls


def fetch_page(page_url: str, referer: str) -> str:
    """在线抓取分页HTML；失败时抛出异常，避免输出不完整名单。"""
    response = requests.get(
        page_url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线合并入口页及动态发现的后续页，并恢复网页原始顺序。"""
    rows = parse_rows(html, page_rule)
    page_urls = discover_page_urls(html, final_url)
    for page_url in page_urls:
        page_rows = parse_rows(fetch_page(page_url, final_url), page_rule)
        if not page_rows:
            raise RuntimeError(f"分页未解析到人物：{page_url}")
        rows.extend(page_rows)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        name = row["name"]
        if name in seen:
            continue
        seen.add(name)
        deduped.append(row)
    return deduped


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
