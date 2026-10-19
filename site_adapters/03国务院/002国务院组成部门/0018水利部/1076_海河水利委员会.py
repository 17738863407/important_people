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
    "rule_id": "1076",
    "page_type": "人物列表完整页",
    "structure_group": "hwcc_leader_iframe_cards_v3",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "iframe_list_direct",
    "collector": "static_http",
    "parser": "page_inline_hwcc_leader_iframe_cards_v3",
    "leader_region_selector": ".leader-container[id]",
    "name_selector": "p:nth-of-type(1)",
    "duty_selector": "p:nth-of-type(2)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "海委领导",
        "end_anchor": "",
        "include_selectors": ["iframe#mainFrame", ".leader-container[id]"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "javascript_click_mapping",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 10,
    },
    "risk_flag": "主页面iframe内直接提供全部姓名职务卡片；详情链接仅从当前页面点击处理器动态映射，不保存固定人物表",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_iframe_cards",
    "locator": {
        "css": {
            "leader_region_selector": ".leader-container[id]",
            "name_selector": "p:nth-of-type(1)",
            "duty_selector": "p:nth-of-type(2)",
            "iframe_selector": "iframe#mainFrame[src]",
        },
        "api": {"enabled": False, "reason": "当前主页面及iframe静态HTML提供完整领导卡片与点击详情映射"},
        "migration": {
            "source": "legacy_fixed_people_and_output_path_removed",
            "verified_status": "verified_current_raw_http_iframe",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def _fetch_html(url: str, referer: str) -> tuple[str, str]:
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
            "Referer": referer,
        },
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_detail_mapping(html: str, base_url: str) -> dict[str, str]:
    pattern = re.compile(
        r'\$\("#(?P<item_id>[A-Za-z0-9_-]+)"\)\.click\(function\(\)\s*\{.*?'
        r'\$\("#mainFrame"\)\.attr\("src"\s*,\s*"(?P<url>[^"]+)"\)',
        re.S,
    )
    return {match.group("item_id"): urljoin(base_url, match.group("url")) for match in pattern.finditer(html)}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """读取主页面的领导iframe，并按卡片DOM顺序提取强字段。"""
    from crawler_core.models import PersonRecord

    main_soup = BeautifulSoup(html, "html.parser")
    iframe = main_soup.select_one("iframe#mainFrame[src]")
    if iframe is None:
        return []
    iframe_url = urljoin(final_url, iframe.get("src", ""))
    iframe_html, iframe_final_url = _fetch_html(iframe_url, final_url)
    iframe_soup = BeautifulSoup(iframe_html, "html.parser")
    detail_mapping = _extract_detail_mapping(html, final_url)

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for card in iframe_soup.select(".leader-container[id]"):
        paragraphs = card.select(":scope > p")
        if len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", paragraphs[0].get_text(" ", strip=True))
        duty = _clean_text(paragraphs[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not duty or name in seen_names:
            continue
        detail_url = detail_mapping.get(str(card.get("id", "")), "")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=f"iframe {iframe_final_url}内leader-container卡片前两段",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
