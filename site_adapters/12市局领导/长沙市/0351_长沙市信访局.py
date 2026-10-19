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
    "rule_id": "0351",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_petition_detail_dl_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changsha_petition_detail_dl_fields_v1",
    "leader_region_selector": "div.xxgk-list li",
    "name_selector": "目录a[href]文本及详情h1",
    "duty_selector": "详情.ldxx dl中的职务标签对应值",
    "detail_link_selector": "div.xxgk-list li a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.xxgk-list"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "static_http", "detail_link_selector": "div.xxgk-list li a[href]", "detail_parser": "page_inline_detail_dl_fields", "detail_name_selector": "h1", "detail_duty_selector": ".ldxx dl", "detail_content_selector": ".leader", "max_detail_links": 50},
    "risk_flag": "详情桌面与移动DOM重复，且同时含职务、分工、简历；只取首个职务dl对应值",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_dl_label_values",
    "locator": {
        "css": {"leader_region_selector": "div.xxgk-list li", "name_selector": "list_anchor_text_equals_detail_h1", "duty_selector": "first_detail_dl_label_duty_value", "detail_link_selector": "same_list_item_anchor_href"},
        "api": {"enabled": False, "reason": "目录及详情原始HTML直接提供姓名、职务和详情链接"},
        "migration": {"source": "legacy_list_to_detail_full_text_scan", "verified_status": "verified_current_online", "behavior_changed": True},
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
    """从详情h1及首个职务dl标签值对读取姓名、原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("h1")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
    duty = ""
    for field in soup.select(".ldxx dl"):
        values = field.select(":scope > dd")
        if len(values) < 2:
            continue
        label = re.sub(r"\s+", "", clean_text(values[0].get_text(" ", strip=True)))
        if label == "职务":
            duty = clean_text(
                re.sub(
                    r"[<＜(（]\s*(?:挂职|兼|主持日常工作)\s*[>＞)）]",
                    "",
                    values[1].get_text(" ", strip=True),
                )
            )
            break
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序逐详情核对姓名，并读取首个职务dl字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["detail_link_selector"]):
        list_name = re.sub(r"\s+", "", clean_text(anchor.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        try:
            name, duty = parse_detail(fetch_detail_html(detail_url))
        except requests.RequestException:
            continue
        name = re.sub(r"\s+", "", name)
        if not name or name != list_name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_directory；detail=first_dl_label_values；duplicate_dom=excluded；work_and_resume=excluded"})
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
