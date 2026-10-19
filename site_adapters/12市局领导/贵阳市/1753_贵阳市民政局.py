from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1753", "page_type": "人物列表完整页", "structure_group": "主负责人及成员目录与详情字段卡片",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".ldone a.lindao[href], #changes2 a.chengyuan[href]", "name_selector": ".ldone .ldh4",
    "duty_selector": ".ldone .ldp", "detail_link_selector": ".ldone a.lindao[href], #changes2 a.chengyuan[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".ldone", "#changes2"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "首页成员仅显示简化党委委员，须按首页顺序读取各详情.ldone完整姓名与职务字段",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_standalone_concurrent_marker(value: str) -> str:
    """删除独立“兼”状态标记，保留具体任职与职级。"""
    return re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", clean_text(value)).strip()


def read_detail_fields(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one("#Zoom .ldone") or soup.select_one(".ldone")
    if block is None:
        return "", ""
    name_node = block.select_one(".ldh4")
    duty_node = block.select_one(".ldp")
    return (
        clean_text(name_node.get_text(" ", strip=True)) if name_node else "",
        clean_standalone_concurrent_marker(duty_node.get_text(" ", strip=True)) if duty_node else "",
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    links = []
    main_link = soup.select_one(".ldone a.lindao[href]")
    if main_link is not None:
        links.append(main_link)
    links.extend(soup.select("#changes2 a.chengyuan[href]"))
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in links:
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not detail_url or detail_url in seen_urls:
            continue
        detail = fetch_html_with_strategy(detail_url, "requests")
        name, duty = read_detail_fields(detail.html)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            raise ValueError(f"详情页缺少可靠姓名或职务字段：{detail.final_url}")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url,
                     "selector_summary": "首页主负责人及成员链接；详情.ldone .ldh4姓名与.ldp完整职务"})
        seen_urls.add(detail_url)
    if not rows:
        raise ValueError("领导页面未发现可验证的人物详情记录")
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
