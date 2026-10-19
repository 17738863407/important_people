from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0723",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_gjj_detail_table_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changsha_gjj_detail_table_fields_v1",
    "leader_region_selector": "div.xxgk-list li",
    "name_selector": "目录a[href]文本及详情表格姓名字段",
    "duty_selector": "详情表格职务字段",
    "detail_link_selector": "div.xxgk-list li a[href]",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": ["div.xxgk-list"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "static_http", "detail_link_selector": "div.xxgk-list li a[href]", "detail_parser": "page_inline_detail_table_label_values", "detail_name_selector": "table姓名标签对应值", "detail_duty_selector": "table职务标签对应值", "detail_content_selector": "table", "max_detail_links": 50},
    "risk_flag": "详情表格同时含职务、工作职责和工作简历；仅采用姓名与职务标签对应值",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_table_label_values",
    "locator": {
        "css": {"leader_region_selector": "div.xxgk-list li", "name_selector": "list_anchor_text_equals_detail_table_name", "duty_selector": "detail_table_duty_label_value", "detail_link_selector": "same_list_item_anchor_href"},
        "api": {"enabled": False, "reason": "目录和详情原始HTML直接提供姓名、职务及详情链接"},
        "migration": {"source": "legacy_directory_online_detail_parser", "verified_status": "verified_current_online", "behavior_changed": True},
    },
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def fetch_detail_html(detail_url: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_detail(detail_html: str) -> tuple[str, str]:
    """从详情表格标签值对读取姓名与原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    cells = [clean_text(cell.get_text(" ", strip=True)) for cell in soup.select("table td, table th")]
    fields: dict[str, str] = {}
    for index, cell in enumerate(cells[:-1]):
        label = re.sub(r"[:：\s\xa0]+", "", cell)
        if label in {"姓名", "职务"}:
            fields[label] = cells[index + 1]
    return re.sub(r"\s+", "", fields.get("姓名", "")), fields.get("职务", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序逐详情核对姓名，并读取职务表格字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["detail_link_selector"]):
        list_name = re.sub(r"\s+", "", clean_text(anchor.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        try:
            detail_name, duty = parse_detail(fetch_detail_html(detail_url))
        except requests.RequestException:
            continue
        if detail_name != list_name or not duty or detail_name in seen:
            continue
        seen.add(detail_name)
        rows.append({"name": detail_name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_directory；detail=table_label_values；work_and_resume=excluded"})
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
