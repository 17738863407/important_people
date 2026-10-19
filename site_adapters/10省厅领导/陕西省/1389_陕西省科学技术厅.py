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


def parse_detail_identity(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    spans = [normalize_space(span.get_text(" ", strip=True)) for span in soup.select(".leader-info span")]
    if len(spans) < 2:
        return "", ""
    return clean_name(spans[0]), clean_duty(spans[1])


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.shaanxi.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_submenu_bounded_detail",
        "collector": "static_http",
        "parser": "page_shaanxi_science_leader_bounded_details_v1",
        "leader_region_selector": "ul.submenu",
        "name_selector": "ul.submenu a span",
        "duty_selector": "detail .leader-info span[2]",
        "detail_link_selector": "ul.submenu a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": ["ul.submenu"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": "ul.submenu a[href]",
            "detail_parser": "detail_shaanxi_science_leader_info_spans_v1",
            "detail_name_selector": ".leader-info span:first-of-type",
            "detail_duty_selector": ".leader-info span:nth-of-type(2)",
            "detail_content_selector": ".leader-info",
            "max_detail_links": 8,
            "candidate_links": [],
        },
        "risk_flag": "fixed_bounded_detail_chain_8",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "ul.submenu",
                "name_selector": "ul.submenu a span",
                "duty_selector": "detail .leader-info span[2]",
                "detail_link_selector": "ul.submenu a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": ["ul.submenu"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "左侧委厅领导列表给出个人页，个人页 .leader-info 直接列出姓名和职务"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


PAGE_RULE = build_page_rule(
    "1389",
    
)


def resolve_leader_navigation(html: str, final_url: str) -> tuple[str, str]:
    """入口页使用 meta refresh 时，在线取得承载委厅领导子菜单的首位详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("ul.submenu a[href]"):
        return html, final_url
    for meta in soup.select("meta[http-equiv][content]"):
        if str(meta.get("http-equiv") or "").lower() != "refresh":
            continue
        match = re.search(r"\burl\s*=\s*(?P<target>.+)$", str(meta.get("content") or ""), re.I)
        if not match:
            continue
        target_url = urljoin(final_url, match.group("target").strip(" '\""))
        try:
            return fetch_html(target_url), target_url
        except Exception:
            return html, final_url
    return html, final_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    html, navigation_url = resolve_leader_navigation(html, final_url)
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul.submenu")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]")[:8]:
        listed_name = clean_name(link.get_text(" ", strip=True))
        if not is_name(listed_name) or listed_name in seen_names:
            continue
        detail_url = urljoin(navigation_url, link.get("href", ""))
        name = listed_name
        duty = ""
        try:
            detail_name, duty = parse_detail_identity(fetch_html(detail_url))
            if is_name(detail_name):
                name = detail_name
        except Exception:
            duty = ""
        if not duty or len(duty) > 120:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=ul.submenu；fields=8 leader links + detail .leader-info spans；detail_chain=8",
                "order": str(len(rows) + 1),
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
