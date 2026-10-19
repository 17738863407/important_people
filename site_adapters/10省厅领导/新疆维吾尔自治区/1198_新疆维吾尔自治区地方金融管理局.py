from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1198",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_finance_directory_detail_duty_cell",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_finance_directory_detail_duty_cell_v1",
    "leader_region_selector": ".gknr_list",
    "name_selector": ".gknr_list dd a[href]",
    "duty_selector": "详情表格含【职务】的td后续文本行",
    "detail_link_selector": ".gknr_list dd a[href]",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "", "include_selectors": [".gknr_list dd a[href]", "详情职务td"], "exclude_selectors": ["发布日期", "相关稿件", "页脚"]},
    "detail_strategy": {"required": True, "mode": "directory_details", "detail_collector_type": "static_http", "detail_link_selector": ".gknr_list dd a[href]", "detail_name_selector": "详情标题", "detail_duty_selector": "【职务】td后续文本行", "detail_content_selector": "含【职务】的td", "max_detail_links": 50},
    "risk_flag": "详情职务可能跨多行；只读取【职务】所在td的后续文本行，保持网页顺序并排除相关稿件与页脚",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".gknr_list", "name_selector": "dd a[href]", "duty_selector": "详情【职务】td文本行", "detail_link_selector": "dd a[href]", "content_scope": {"start_anchor": "【职务】", "end_anchor": "当前td结束", "include_selectors": ["td"], "exclude_selectors": ["相关稿件", "页脚"]}},
        "api": {"enabled": False, "reason": "当前静态HTML目录与详情表格直接提供姓名、职务和链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def _fetch_detail(url: str, referer: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_duty(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    marker = soup.find(string=lambda value: _clean_text(value) == "【职务】")
    if marker is None or marker.parent is None:
        return ""
    cell = marker.parent if marker.parent.name == "td" else marker.parent.find_parent("td")
    if cell is None:
        return ""
    lines = [_clean_text(value) for value in cell.stripped_strings]
    lines = [value for value in lines if value and value != "【职务】"]
    return "；".join(lines)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序在线读取详情页【职务】单元格。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".gknr_list dd a[href]"):
        name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or name in seen:
            continue
        detail_html, detail_url = _fetch_detail(urljoin(base_url, str(link.get("href", ""))), base_url)
        duty = _extract_duty(detail_html)
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": "custom_xinjiang_finance_directory_detail_duty_cell_v1", "selector_summary": ".gknr_list目录；详情【职务】td后续文本行"})
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
