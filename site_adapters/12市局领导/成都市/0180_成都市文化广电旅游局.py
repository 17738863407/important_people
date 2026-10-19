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
    "rule_id": "0180",
    "page_type": "人物目录详情页",
    "structure_group": "cdwglj_leader_directory_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "chrome_cdp",
    "leader_region_selector": "div.list.ejs_list > ul",
    "detail_link_selector": "div.list.ejs_list > ul > li > a.doctitle[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_content_selector": "#text_content",
        "max_detail_links": 30,
    },
    "risk_flag": "职务位于详情正文首个人物段落，必须以列表页姓名为边界截取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_without_layout_space(value: str) -> str:
    """清理 HTML 排版产生的空白，不改变人物或职务语义。"""
    return re.sub(r"\s+", "", value or "")


def extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """从详情正文首个人物段落中截取姓名后的原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("#text_content")
    if content is None:
        return ""
    normalized_name = compact_without_layout_space(expected_name)
    candidates: list[str] = []
    for node in content.find_all(["p", "div", "span"], recursive=True):
        text = compact_without_layout_space(node.get_text("", strip=True))
        if not text.startswith(normalized_name) or len(text) <= len(normalized_name):
            continue
        candidate = text[len(normalized_name) :].lstrip("：:，,；;")
        biography_markers = ("男，", "女，", "族，", "学历", "中共党员")
        if any(marker in candidate for marker in biography_markers):
            continue
        if re.search(r"\d{4}年\d{1,2}月生", candidate):
            continue
        candidates.append(candidate)
    if candidates:
        shortest = min(candidates, key=len)
        return shortest
    content_text = compact_without_layout_space(content.get_text("", strip=True))
    current_match = re.search(r"现任[^。]*。", content_text)
    if current_match:
        return current_match.group(0)
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录页 DOM 顺序访问详情页并提取姓名、职务和真实详情链接。"""
    from crawler_core.fetcher import fetch_by_chrome_debug

    soup = BeautifulSoup(html, "html.parser")
    link_selector = str(page_rule.get("detail_link_selector") or "")
    links = soup.select(link_selector)
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for order, link in enumerate(links, start=1):
        name = compact_without_layout_space(link.get_text("", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not name or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_by_chrome_debug(detail_url)
        duty = extract_detail_duty(detail_result.html, name)
        if not duty:
            raise RuntimeError(f"详情页未找到姓名边界明确的职务段落：{detail_result.final_url}")
        rows.append(
            {
                "order": str(order),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_cdwglj_leader_directory_detail_v1",
            }
        )
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
