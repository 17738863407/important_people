from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.hunan.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_to_detail",
        "collector": "static_http",
        "parser": "page_hunan_education_leader_detail_position_v1",
        "leader_region_selector": "a[href*='/jgld/']",
        "name_selector": "leader list link text",
        "duty_selector": "detail 职务职级",
        "detail_link_selector": "a[href*='/jgld/']",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": True,
            "mode": "list_to_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": "a[href*='/jgld/']",
            "detail_name_selector": "detail 名称/标题",
            "detail_duty_selector": "detail 职务职级",
            "detail_content_selector": "body",
            "max_detail_links": 12,
        },
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "a[href*='/jgld/']",
                "name_selector": "leader list link text",
                "duty_selector": "detail 职务职级",
                "detail_link_selector": "a[href*='/jgld/']",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网列表页和详情页均为静态 HTML"},
        },
    }


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", clean_name(text)))


def fetch_detail(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_detail(name_hint: str, detail_html: str) -> tuple[str, str] | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = normalize_space(soup.get_text(" ", strip=True))
    name = clean_name(name_hint)
    duty = ""
    duty_start = re.search(r"职务职级[:：]", text)
    duty_end = re.search(r"分工[:：]", text)
    if duty_start and duty_end and duty_start.end() <= duty_end.start():
        duty = normalize_space(text[duty_start.end() : duty_end.start()])
    duty = duty.rstrip("。")
    if not is_name(name) or not duty:
        return None
    return name, duty


def collect_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href*='/jgld/']"):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, link.get("href", "").strip())
        parsed_detail = urlparse(detail_url)
        if (
            not is_name(name)
            or detail_url in seen
            or parsed_detail.netloc.lower() != urlparse(base_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(base_url)[0].rstrip('/')
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            continue
        seen.add(detail_url)
        links.append((name, detail_url))
    return links[:12]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for name_hint, detail_url in collect_links(soup, base_url):
        result = extract_detail(name_hint, fetch_detail(detail_url))
        if not result:
            continue
        name, duty = result
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=a[href*=jgld]；detail=职务职级",
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
    rule_id_value = "1335"
    main(rule_id_value)
