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
    return re.sub(r"\s+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", duty)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kxjst.jiangsu.gov.cn",
        "page_type": "人物表格页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_table_cards_direct",
        "collector": "static_http",
        "parser": "page_jiangsu_science_leader_table_cards_v1",
        "leader_region_selector": ".fding1 ul.cf",
        "name_selector": ".fding1 li.ldfg .ldtext a first text segment",
        "duty_selector": ".fding1 li.ldfg .ldtext a remaining text segments",
        "detail_link_selector": ".fding1 li.ldfg .ldtext a[href]",
        "content_scope": {
            "start_anchor": "领导及分工",
            "end_anchor": "",
            "include_selectors": [".fding1 ul.cf"],
            "exclude_selectors": [".main-content-left", "footer"],
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
                "leader_region_selector": ".fding1 ul.cf",
                "name_selector": ".fding1 li.ldfg .ldtext a first text segment",
                "duty_selector": ".fding1 li.ldfg .ldtext a remaining text segments",
                "detail_link_selector": ".fding1 li.ldfg .ldtext a[href]",
                "content_scope": {
                    "start_anchor": "领导及分工",
                    "end_anchor": "",
                    "include_selectors": [".fding1 ul.cf"],
                    "exclude_selectors": [".main-content-left", "footer"],
                },
            },
            "api": {"enabled": False, "reason": "领导及分工表格卡片直接列出姓名、职务和详情链接"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".fding1 ul.cf")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select("li.ldfg"):
        link = item.select_one(".ldtext a[href]")
        if link is None:
            continue
        parts = [normalize_space(part) for part in link.stripped_strings]
        parts = [part for part in parts if part]
        if len(parts) < 2:
            continue
        name = clean_name(parts[0])
        duty = clean_duty("".join(parts[1:]))
        if not is_name(name) or name in seen_names or not duty or len(duty) > 120:
            continue
        detail_url = urljoin(str(page_rule.get("url", "")) or final_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(str(page_rule.get("url", "")) or final_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not re.search(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html$", detail.path)
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
                "selector_summary": "strategy=custom_parse_page；region=.fding1 ul.cf；fields=li.ldfg .ldtext a text segments；detail_chain=0",
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
    rule_id_value = "1403"
    main(rule_id_value)
