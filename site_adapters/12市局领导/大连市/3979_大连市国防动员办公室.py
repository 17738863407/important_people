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
    "rule_id": "3979", "domain": "rfb.dl.gov.cn", "page_type": "领导列表转人物详情",
    "structure_group": "dalian_defense_mobilization_leader_details", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_to_detail", "collector": "static_http",
    "parser": "page_dalian_defense_mobilization_details_v1", "leader_region_selector": ".introduce_list .zfxxgk_zdgkc",
    "name_selector": "a", "duty_selector": ".art_con p:first-of-type",
    "content_scope": {"include_selectors": [".introduce_list .zfxxgk_zdgkc"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": True, "mode": "dynamic_links", "detail_content_selector": ".art_con"},
    "risk_flag": "入口页仅列姓名，须按原始顺序访问动态人物详情页取得首个现职段落",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".introduce_list .zfxxgk_zdgkc", "detail_selector": ".art_con p"}},
}


def normalize_text(value: str) -> str:
    """清理详情正文中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现人物详情链接，并从详情正文首个非空段落取得现职证据。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".introduce_list .zfxxgk_zdgkc")
    if region is None:
        raise RuntimeError("入口页未找到领导介绍区域")

    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in region.select("a[href]"):
        name = normalize_text(anchor.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        duty = ""
        for paragraph in detail_soup.select(".art_con p"):
            text = normalize_text(paragraph.get_text(" ", strip=True))
            if text and not text.startswith(("负责", "主持", "分管", "联系")):
                duty = text
                break
        if not duty:
            raise RuntimeError(f"人物详情页未取得现职段落：{detail_result.final_url}")
        rows.append({
            "name": name, "duty": duty, "evidence": duty,
            "detail_url": detail_result.final_url, "parser": str(page_rule.get("parser", "")),
            "selector_summary": "领导介绍动态链接→详情正文首个现职段落",
        })
    if not rows:
        raise RuntimeError("领导介绍区域未解析出有效人物")
    return rows


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
