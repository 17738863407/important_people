from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0488", "page_type": "人物目录详情页", "structure_group": "人物目录链接与详情职务标题姓名字段",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".scroll_main .zfxxgk_zdgkc", "name_selector": "a[title]", "duty_selector": "#gy_lmy_right > ul.main_322:first-of-type li",
    "detail_link_selector": ".scroll_main .zfxxgk_zdgkc a[title][href]",
    "content_scope": {"start_anchor": "机构领导", "end_anchor": "", "include_selectors": [".scroll_main .zfxxgk_zdgkc"], "exclude_selectors": [".dl_nav", ".footer"]},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 20},
    "risk_flag": "详情普通requests跳转空页，须使用raw_http；第一职务标题后另有分工标题，不得混入", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def read_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#gy_lmy_right")
    if root is None:
        return "", ""
    name = ""
    for block in root.select(".main_32321"):
        block_text = clean_text(block.get_text(" ", strip=True))
        if block_text.replace(" ", "").startswith("姓名:") or block_text.replace(" ", "").startswith("姓名："):
            value = block.select_one("span")
            name = clean_text(value.get_text(" ", strip=True) if value is not None else "").replace(" ", "")
            break
    titles = root.find_all("ul", class_="main_322", recursive=False)
    duty_node = titles[0].find("li") if titles else None
    duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物目录顺序抓取详情，并读取姓名字段与第一职务标题。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".scroll_main .zfxxgk_zdgkc a[title][href]"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        name, duty = read_detail(detail.html)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or not duty or name in seen:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url, "selector_summary": "人物目录链接；详情姓名字段及第一main_322职务标题"})
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
