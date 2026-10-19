from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0542", "page_type": "人物目录详情页", "structure_group": "人物目录链接与详情姓名职务字段块",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc", "name_selector": "dd > a[href] p, dd > a[href][title]", "duty_selector": ".profile_right .name .p2",
    "detail_link_selector": ".zfxxgk_zdgkc dd > a[href]",
    "content_scope": {"start_anchor": "部门领导", "end_anchor": "网站地图", "include_selectors": [".zfxxgk_zdgkc"], "exclude_selectors": [".dl_nav", ".footer"]},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "详情普通requests返回非目标页面，须以raw_http读取.profile_right姓名职务字段", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    text = str(value or "").replace("\u200b", "")
    return re.sub(r"[\s\u3000\xa0\u2000-\u200a]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取详情，并读取姓名和职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".zfxxgk_zdgkc dd > a[href]"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(detail.html, "html.parser")
        name_node = detail_soup.select_one(".profile_right .name .p1")
        duty_node = detail_soup.select_one(".profile_right .name .p2")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "").strip("。")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or not duty or name in seen:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url, "selector_summary": "人物目录链接；详情.profile_right姓名p1与职务p2"})
        seen.add(name)
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
