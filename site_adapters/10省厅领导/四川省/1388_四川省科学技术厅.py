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
    duty = re.sub(r"^四川省科学技术厅", "", duty)
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
    for node in soup.find_all(["p", "td", "h1", "h2", "h3", "div"]):
        text = normalize_space(node.get_text(" ", strip=True))
        if len(text) > 80 or name not in text or "政策法规" in text:
            continue
        match = re.match(rf"(?P<duty>.+?)\s+{re.escape(name)}$", text)
        if match:
            return clean_duty(match.group("duty"))
        match = re.match(rf"(?P<duty>.+?)\s+{re.escape(name)}\s+{re.escape(name)}", text)
        if match:
            return clean_duty(match.group("duty"))
    return ""


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.sc.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_directory_bounded_detail",
        "collector": "static_http",
        "parser": "page_sichuan_science_leader_bounded_details_v1",
        "leader_region_selector": ".content ul.list-unstyled",
        "name_selector": ".content ul.list-unstyled li a",
        "duty_selector": "detail short text 职务 姓名",
        "detail_link_selector": ".content ul.list-unstyled li a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [".content ul.list-unstyled"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".content ul.list-unstyled li a[href]",
            "detail_parser": "detail_sichuan_science_short_duty_name_v1",
            "detail_name_selector": "",
            "detail_duty_selector": "short tag text before name",
            "detail_content_selector": "",
            "max_detail_links": 0,
            "candidate_links": [],
        },
        "risk_flag": "online_bounded_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".content ul.list-unstyled",
                "name_selector": ".content ul.list-unstyled li a",
                "duty_selector": "detail short text 职务 姓名",
                "detail_link_selector": ".content ul.list-unstyled li a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [".content ul.list-unstyled"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导介绍目录仅列姓名，职务位于对应个人页开头短文本"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content ul.list-unstyled")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("li a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        duty = ""
        try:
            duty = parse_detail_duty(fetch_html(detail_url), name)
        except Exception:
            duty = ""
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
                "selector_summary": "strategy=custom_parse_page；region=.content leader ul；fields=9 directory links + detail short duty-name text；detail_chain=9",
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
    rule_id_value = "1388"
    main(rule_id_value)
