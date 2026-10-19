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
    "rule_id": "1472",
    "page_type": "人物列表完整页",
    "structure_group": "guizhou_forestry_leader_window_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_guizhou_forestry_leader_detail_v2",
    "leader_region_selector": ".ldzcNav",
    "name_selector": ".ldzcNav li a[href] strong",
    "duty_selector": "详情页meta[name='Description']中的现任句",
    "detail_link_selector": ".ldzcNav li a[href]",
    "content_scope": {
        "start_anchor": "局领导",
        "end_anchor": "组织机构",
        "include_selectors": [".ldzcNav"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_detail",
        "detail_collector_type": "raw_http",
        "detail_link_selector": ".ldzcNav li a[href]",
        "detail_name_selector": "meta[name='ArticleTitle'], meta[name='Keywords']",
        "detail_duty_selector": "meta[name='Description']中的现任句",
        "detail_content_selector": "meta[name='Description']",
        "max_detail_links": 10,
    },
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "领导之窗入口同时呈现当前人物详情与左侧全体领导目录，必须按ldzcNav目录顺序逐页提取现任句",
}


def clean_text(value: object) -> str:
    """压缩HTML排版空白，并清理全角空格。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def collect_leader_links(html: str, final_url: str) -> list[tuple[str, str]]:
    """按领导之窗左侧目录的DOM顺序收集姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".ldzcNav li a[href]")

    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        name_node = link.select_one("strong")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
        detail_url = urljoin(final_url, clean_text(link.get("href")))
        key = (name, detail_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not detail_url or key in seen:
            continue
        seen.add(key)
        candidates.append(key)
    return candidates


def parse_detail(name: str, detail_url: str) -> dict[str, str] | None:
    """从当前人物详情页的描述元数据提取完整现任职务句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    fetch_result = fetch_by_raw_requests(detail_url, timeout=60)
    soup = BeautifulSoup(fetch_result.html, "html.parser")
    description_node = soup.select_one("meta[name='Description']")
    description = clean_text(description_node.get("content") if description_node is not None else "")
    compact_description = description.replace(" ", "")
    if name not in compact_description:
        return None
    match = re.search(r"现任[^。]*。", description)
    if match is None:
        return None
    evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0))).removesuffix("。").strip()
    return {
        "name": name,
        "duty": evidence,
        "detail_url": fetch_result.final_url,
        "evidence": evidence,
        "confidence": "high",
        "parser": "page_inline_guizhou_forestry_leader_detail_v2",
        "selector_summary": "领导之窗.ldzcNav目录DOM顺序；详情页meta[name=Description]现任句",
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """依次读取入口页当前领导及其个人详情页，保持入口页原始顺序。"""
    rows: list[dict[str, str]] = []
    for name, detail_url in collect_leader_links(html, final_url):
        try:
            row = parse_detail(name, detail_url)
        except Exception as error:
            print(f"跳过详情页采集失败的人物：{name}；{detail_url}；{error}")
            continue
        if row is not None:
            rows.append(row)
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
