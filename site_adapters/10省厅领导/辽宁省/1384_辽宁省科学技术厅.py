from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

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


def clean_duty(text: str, organization: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(rf"^{re.escape(organization)}", "", duty)
    duty = re.split(r"[,，]|负责", duty, maxsplit=1)[0]
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_detail_duty(detail_html: str, organization: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".TRS_Editor") or soup
    text = normalize_space(region.get_text(" ", strip=True))
    if organization not in text:
        return ""
    return clean_duty(text, organization)


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.ln.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "leader_cards_bounded_detail",
        "collector": "static_http",
        "parser": "page_liaoning_science_leader_bounded_details_v1",
        "leader_region_selector": "#zf_xxgkr .oflow-hd",
        "name_selector": "#zf_xxgkr .oflow-hd dd.ldname a",
        "duty_selector": "detail .TRS_Editor text after 辽宁省科学技术厅",
        "detail_link_selector": "#zf_xxgkr .oflow-hd dd.ldname a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": ["#zf_xxgkr .oflow-hd"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": "#zf_xxgkr .oflow-hd dd.ldname a[href]",
            "detail_parser": "detail_liaoning_science_trs_editor_duty_sentence_v1",
            "detail_name_selector": "",
            "detail_duty_selector": ".TRS_Editor",
            "detail_content_selector": ".TRS_Editor",
            "max_detail_links": 50,
            "candidate_links": [],
        },
        "risk_flag": "bounded_detail_chain_online",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#zf_xxgkr .oflow-hd",
                "name_selector": "#zf_xxgkr .oflow-hd dd.ldname a",
                "duty_selector": "detail .TRS_Editor text after 辽宁省科学技术厅",
                "detail_link_selector": "#zf_xxgkr .oflow-hd dd.ldname a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": ["#zf_xxgkr .oflow-hd"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "部门领导模块只列姓名，职务位于对应详情页正文"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zf_xxgkr .oflow-hd")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    organization = str(page_rule.get("organization", ""))
    for link in region.select("dd.ldname a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        duty = ""
        try:
            duty = parse_detail_duty(fetch_html(detail_url), organization)
        except Exception:
            duty = ""
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
        if not duty or len(duty) > 120:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#zf_xxgkr .oflow-hd；fields=9 leader links + detail .TRS_Editor duty sentence；detail_chain=9",
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
    rule_id_value = "1384"
    main(rule_id_value)
