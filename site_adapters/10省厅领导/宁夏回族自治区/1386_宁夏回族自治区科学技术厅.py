from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"[\s\u200b]+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = duty.replace("（挂职）", "").replace("(挂职)", "")
    duty = duty.replace("党组书记 厅长", "党组书记、厅长")
    duty = duty.replace("党组成员 副厅长", "党组成员、副厅长")
    duty = duty.replace("党组成员 驻厅", "党组成员、驻厅")
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def split_leader_text(text: str) -> tuple[str, str]:
    normalized = normalize_space(text).lstrip("》").strip()
    match = re.match(r"(?P<duty>.+?)\s*[:：]\s*(?P<name>[\u200b\s\u4e00-\u9fff·]{2,8})$", normalized)
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_duty(match.group("duty"))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.nx.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_list_duty_name_direct",
        "collector": "static_http",
        "parser": "page_ningxia_science_leader_duty_name_links_v1",
        "leader_region_selector": "ul.list_ul.fs",
        "name_selector": "ul.list_ul.fs li a text after colon",
        "duty_selector": "ul.list_ul.fs li a text before colon",
        "detail_link_selector": "ul.list_ul.fs li a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": ["ul.list_ul.fs"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": "",
            "detail_parser": "",
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
        },
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "ul.list_ul.fs",
                "name_selector": "ul.list_ul.fs li a text after colon",
                "duty_selector": "ul.list_ul.fs li a text before colon",
                "detail_link_selector": "ul.list_ul.fs li a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": ["ul.list_ul.fs"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导信息列表已直接列出职务和姓名"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul.list_ul.fs")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("li a[href]"):
        name, duty = split_leader_text(link.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names or not duty or len(duty) > 120:
            continue
        base_url = str(page_rule.get("url", "")) or final_url
        detail_url = urljoin(base_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(base_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not detail.path.lower().endswith((".html", ".htm"))
        ):
            detail_url = ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=ul.list_ul.fs；fields=a text duty:name；detail_chain=0",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1386"
    main(rule_id_value)
