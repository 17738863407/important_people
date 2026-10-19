from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2264",
    "page_type": "人物列表完整页",
    "structure_group": "渲染后人物链接与详情简介职务",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_detail",
    "collector": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "playwright",
    "parser": "builtin_parse_page",
    "leader_region_selector": 'a.document-number[href*="/gkmlpt/content/"]',
    "name_selector": "a.document-number",
    "duty_selector": ".article-content",
    "detail_link_selector": 'a.document-number[href*="/gkmlpt/content/"]',
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["a.document-number", ".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "入口人物链接由接口渲染，必须浏览器复核后逐详情在线解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_detail_duty(html: str, name: str) -> str:
    """从详情简介中提取姓名之后、分工动作之前的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    for content in soup.select(".article-content"):
        text = clean_text(content.get_text(" ", strip=True))
        match = re.search(
            rf"简介\s*[：:]\s*{re.escape(name)}\s*[，,]\s*"
            r"(?P<duty>.+?)(?=[，,](?:主持|分管|负责|联系|协助)|[。])",
            text,
        )
        if match is not None:
            return clean_text(match.group("duty")).strip("，,。；;：:")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按渲染后入口页人物链接顺序抓取并解析详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    if not html:
        entry_result = fetch_html_with_strategy(
            str(page_rule.get("url", "")),
            "playwright",
            timeout=60,
            browser_render_wait_ms=4000,
        )
        html = entry_result.html
        final_url = entry_result.final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_urls: set[str] = set()

    for anchor in soup.select('a.document-number[href*="/gkmlpt/content/"]'):
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(anchor.get("href") or ""))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name)
            or name in seen
            or detail_url in seen_urls
        ):
            continue
        detail_result = fetch_html_with_strategy(
            detail_url,
            "playwright",
            timeout=60,
            browser_render_wait_ms=2000,
        )
        duty = extract_detail_duty(detail_result.html, name)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "selector_summary": "渲染后入口a.document-number人物链接及详情.article-content简介职务",
            }
        )
        seen.add(name)
        seen_urls.add(detail_url)

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
