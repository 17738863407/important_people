from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0610",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_to_detail",
    "leader_region_selector": "#postList table.table-content",
    "detail_link_selector": "td.first-td a[href]",
    "detail_content_selector": ".article-content",
    "detail_timeout_seconds": 30,
    "risk_flag": "入口名单由动态接口渲染；职务只在各人物详情正文的完整现任句中提取",
    "confidence": "high",
    "filter_policy": "weak_allow_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空白，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按动态入口名单顺序在线抓取详情页并提取完整“现任……”句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到动态渲染后的领导名单表格")

    base_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        name = clean_name(link.get_text(" ", strip=True))
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if "/gkmlpt/content/" not in detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    rows: list[dict] = []
    seen_names: set[str] = set()
    for expected_name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        title_node = detail_soup.select_one("title")
        detail_name = clean_name(title_node.get_text(" ", strip=True) if title_node else "")
        if detail_name != expected_name:
            raise RuntimeError(
                f"详情页标题与入口姓名不一致：{expected_name} / {detail_name} / {detail_url}"
            )

        content = detail_soup.select_one(page_rule["detail_content_selector"])
        content_text = clean_text(content.get_text(" ", strip=True) if content else "")
        match = re.search(r"现任[^。]*。", content_text)
        if not match:
            raise RuntimeError(f"详情正文未找到完整现任句：{detail_url}")
        evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0))).removesuffix("。").strip()
        if expected_name in seen_names:
            continue

        seen_names.add(expected_name)
        rows.append(
            {
                "name": expected_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_guangzhou_police_online_current_sentence_v2",
                "selector_summary": (
                    "entry=#postList table.table-content td.first-td a[href]；"
                    "detail=.article-content内完整现任句"
                ),
            }
        )

    if not rows:
        raise RuntimeError("领导详情页未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
