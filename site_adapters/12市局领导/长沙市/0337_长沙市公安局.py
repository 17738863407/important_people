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
    "rule_id": "0337",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_public_security_detail_dl_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changsha_public_security_detail_dl_fields_v1",
    "leader_region_selector": "div.xxgk-list li",
    "name_selector": "目录a[href]文本及详情h1同志简介标题",
    "duty_selector": "详情.wrap_right dl中的职务标签对应值",
    "detail_link_selector": "div.xxgk-list li a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.xxgk-list"],
        "exclude_selectors": ["header", "footer", "script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.xxgk-list li a[href]",
        "detail_parser": "page_inline_detail_dl_fields",
        "detail_name_selector": "h1",
        "detail_duty_selector": ".wrap_right dl",
        "detail_content_selector": ".wrap_right",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页同时含职务、简历和工作分工；仅采用职务dl对应值",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_dl_label_values",
    "locator": {
        "css": {
            "leader_region_selector": "div.xxgk-list li",
            "name_selector": "list_anchor_text_equals_detail_h1_name",
            "duty_selector": "detail_dl_label_duty_value",
            "detail_link_selector": "same_list_item_anchor_href",
        },
        "api": {"enabled": False, "reason": "目录及详情原始HTML直接提供姓名、职务和详情链接"},
        "migration": {
            "source": "legacy_list_to_detail_full_text_scan",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def fetch_detail_html(detail_url: str) -> str:
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_detail(detail_html: str) -> tuple[str, str]:
    """从详情标题和dl标签值对读取姓名、原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = clean_text(soup.select_one("h1").get_text(" ", strip=True) if soup.select_one("h1") else "")
    name = re.sub(r"同志简介$", "", title).strip()
    duty = ""
    for field in soup.select(".wrap_right dl"):
        values = field.select(":scope > dd")
        if len(values) < 2:
            continue
        label = re.sub(r"\s+", "", clean_text(values[0].get_text(" ", strip=True)))
        if label == "职务":
            duty = clean_text(values[1].get_text(" ", strip=True))
            break
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序逐详情核对姓名，并读取职务dl字段。"""
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
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "source_text": duty,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=leader_directory；detail=dl_label_values；resume_and_work=excluded",
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
