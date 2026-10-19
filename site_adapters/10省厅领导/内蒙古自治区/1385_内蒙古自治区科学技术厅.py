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


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = normalize_space(soup.get_text(" ", strip=True))
    match = re.search(rf"{re.escape(name)}\s+(?P<duty>(?:厅党组|[一二三四]级).{{2,40}}?)\s+领导班子", text)
    if match:
        return clean_duty(match.group("duty"))

    intro = soup.select_one(".trs_editor_view")
    intro_text = normalize_space(intro.get_text(" ", strip=True)) if intro else text
    match = re.search(r"现任内蒙古自治区科学技术厅(?P<duty>[^。；;]+)", intro_text)
    return clean_duty(match.group("duty")) if match else ""


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.nmg.gov.cn",
        "page_type": "多人物详情合并页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "leader_summary_bounded_detail",
        "collector": "static_http",
        "parser": "page_inner_mongolia_science_leader_bounded_details_v1",
        "leader_region_selector": ".zzjg_idx_ldxx",
        "name_selector": ".zzjg_idx_ldxx a[title]",
        "duty_selector": "detail text between name and 领导班子",
        "detail_link_selector": ".zzjg_idx_ldxx a[href][title]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [".zzjg_idx_ldxx"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".zzjg_idx_ldxx a[href][title]",
            "detail_parser": "detail_inner_mongolia_science_name_duty_before_leader_team_v1",
            "detail_name_selector": "",
            "detail_duty_selector": "detail text between name and 领导班子",
            "detail_content_selector": "",
            "max_detail_links": 6,
            "candidate_links": [],
        },
        "risk_flag": "fixed_bounded_detail_chain_6",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".zzjg_idx_ldxx",
                "name_selector": ".zzjg_idx_ldxx a[title]",
                "duty_selector": "detail text between name and 领导班子",
                "detail_link_selector": ".zzjg_idx_ldxx a[href][title]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [".zzjg_idx_ldxx"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "首页领导模块有详情链接，统一从详情页结构读取职务"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def collect_leader_links(soup: BeautifulSoup, final_url: str) -> list[tuple[str, str]]:
    region = soup.select_one(".zzjg_idx_ldxx")
    if region is None:
        return []

    links: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href][title]"):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names:
            continue
        seen_names.add(name)
        links.append((name, urljoin(final_url, link.get("href", ""))))
    return links[:6]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for name, detail_url in collect_leader_links(soup, final_url):
        duty = ""
        try:
            duty = parse_detail_duty(fetch_html(detail_url), name)
        except Exception:
            duty = ""
        if not duty or len(duty) > 120:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.zzjg_idx_ldxx；fields=6 leader links + detail name duty before 领导班子；detail_chain=6",
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
    rule_id_value = "1385"
    main(rule_id_value)
