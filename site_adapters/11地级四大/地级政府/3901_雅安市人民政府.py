from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3901",
    "page_type": "市委市政府并列领导卡片",
    "structure_group": "yaan_dual_leader_card_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "scoped_cards",
    "collector": "requests",
    "parser": "page_inline_yaan_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader-ul",
    "name_selector": "li h1 a[href]",
    "duty_selector": "li > p",
    "detail_link_selector": "li h1 a[href]",
    "fallback_timeout_seconds": 45,
    "risk_flag": "页面并列市委与市政府两套同结构卡片且含跨组重复人物；须按职务字段的市人民政府语义锁定政府组",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """锁定政府职务卡片组并按原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")

    def find_government_region(document: BeautifulSoup) -> object:
        labels = document.select(".notice-le .tab-hd .tab-nav > li")
        regions = document.select(".notice-le .tab-bd > .tab-pal .leader-ul")
        for index, label in enumerate(labels):
            label_text = clean_text(label.get_text(" ", strip=True))
            if label_text == "雅安市政府领导" and index < len(regions):
                return regions[index]
        return None

    region = find_government_region(soup)
    if region is None:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            page_rule["url"],
            timeout=int(page_rule["fallback_timeout_seconds"]),
            verify=False,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        soup = BeautifulSoup(response.text, "lxml")
        region = find_government_region(soup)
    if region is None:
        raise RuntimeError("未定位到雅安市政府领导卡片组")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select("li"):
        link = card.select_one("h1 a[href]")
        duty_node = card.find("p", recursive=False)
        name = clean_name(link.get_text(" ", strip=True) if link else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = clean_text(link.get("href")) if link else ""
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or "市政府" not in duty:
            continue
        if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "市人民政府职务语义锁定.leader-ul；卡片h1姓名与直属p职务",
            }
        )

    if not rows:
        raise RuntimeError("雅安市政府领导卡片组未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
