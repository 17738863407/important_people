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

PAGE_RULE = {
    "rule_id": "2951",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom",
    "leader_region_selector": "div.zfxxgkldjj",
    "detail_link_selector": 'a[href*="/c108585/"]',
    "detail_content_selector": "div.zfxxcontent-txt",
    "detail_fetch_mode": "chrome_cdp",
    "detail_strategy": {"required": True, "mode": "custom_online"},
    "risk_flag": "普通HTTP与无头Playwright受412防护，使用Chrome CDP在线渲染",
    "confidence": "high",
}


def clean_text(text: str) -> str:
    """合并网页排版空白，不改变原文语义。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介区的页面顺序读取详情页，并提取完整现任职务原句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        raise RuntimeError("未找到领导简介区域")

    links = region.select(str(page_rule["detail_link_selector"]))
    if not links:
        raise RuntimeError("领导简介区域未发现人物详情链接")

    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = clean_text(str(link.get("href") or ""))
        detail_url = urljoin(final_url, href)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            raise RuntimeError(f"第{source_order}个人物姓名格式异常：{name or '空值'}")
        if not href or detail_url in seen_urls:
            raise RuntimeError(f"第{source_order}个人物详情链接为空或重复：{name}")
        seen_urls.add(detail_url)

        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy=str(page_rule["detail_fetch_mode"]),
            timeout=45,
        )
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        content = detail_soup.select_one(str(page_rule["detail_content_selector"]))
        if content is None:
            raise RuntimeError(f"详情页未找到正文区域：{name}")
        detail_text = clean_text(content.get_text(" ", strip=True))
        if name not in detail_text:
            raise RuntimeError(f"详情页正文无法回指姓名：{name}")
        evidence_match = re.search(r"现(?:挂职)?任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"详情页正文未找到现任职务原句：{name}")
        raw_evidence = clean_text(evidence_match.group(0))
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            raw_evidence,
        ).strip()
        duty = re.sub(r"^现(?:挂职)?任", "", raw_evidence).removesuffix("。")

        rows.append(
            {
                "order": str(source_order),
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": "high",
                "selector_summary": "领导简介区域人物链接+详情页正文现任句",
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
