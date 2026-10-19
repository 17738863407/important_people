from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1305", "page_type": "人物目录详情页", "structure_group": "人物目录链接与详情简介现任句",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail", "collector": "raw_http", "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc li a[title][href]", "name_selector": "a[title]",
    "duty_selector": ".trs_editor_view p", "detail_link_selector": ".zfxxgk_zdgkc li a[title][href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zfxxgk_zdgkc"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "online与requests被导向搜索页，入口和详情均须raw_http；现任句仅在当前人物简介段落提取",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def read_current_sentence(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".trs_editor_view p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if expected_name not in text:
            continue
        match = re.search(r"现任[^。]*。", text)
        if match:
            return clean_text(match.group(0)).removeprefix("现任").removesuffix("。")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".zfxxgk_zdgkc li a[title][href]"):
        name = clean_text(str(link.get("title") or link.get_text(" ", strip=True))).replace(" ", "")
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or detail_url in seen_urls:
            continue
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        evidence = read_current_sentence(detail.html, name)
        if not evidence:
            raise ValueError(f"详情页当前人物简介缺少完整现任句：{detail.final_url}")
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail.final_url,
                     "selector_summary": "机构领导目录链接及详情当前人物简介段落完整现任句"})
        seen_urls.add(detail_url)
    if not rows:
        raise ValueError("机构领导目录未发现可验证的人物详情记录")
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
