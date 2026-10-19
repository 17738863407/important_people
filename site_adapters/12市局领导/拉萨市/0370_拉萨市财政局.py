from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0370",
    "page_type": "人物列表完整页",
    "structure_group": "lasa_finance_mixed_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lasa_finance_mixed_leader_cards_v1",
    "leader_region_selector": ".content .container",
    "name_selector": "div.kp.lead .info p.a a:first-child；.ldlist条目机构名前文本",
    "duty_selector": "主职卡片第二个链接；副职条目机构名后原文",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": "div.kp.lead .info p.a a[href], .ldlist ul.detail li a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "mixed_primary_cards_and_compact_deputy_list",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "primary_cards": "div.kp.lead",
            "primary_heading": ".info p.a",
            "deputy_items": ".ldlist ul.detail li",
            "detail": "a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML直接包含两类完整领导卡片和人物详情链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按主职卡片、随后副职列表的网页顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for card in soup.select("div.kp.lead"):
        heading = card.select_one(".info p.a")
        links = heading.select("a[href]") if heading else []
        if len(links) < 2:
            continue
        name = re.sub(r"\s+", "", normalize_space(links[0].get_text(" ", strip=True)))
        duty = normalize_space(links[1].get_text(" ", strip=True))
        evidence = normalize_space(heading.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        detail_url = urljoin(final_url, str(links[0].get("href", "")).strip())
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "主职卡片.info p.a内姓名链接与职务链接",
            }
        )

    organization_marker = "拉萨市财政局"
    for item in soup.select(".ldlist ul.detail li"):
        link = item.select_one("a[href]")
        if link is None:
            continue
        evidence = normalize_space(link.get_text(" ", strip=True))
        if organization_marker not in evidence:
            continue
        name_text, duty_text = evidence.split(organization_marker, 1)
        name = re.sub(r"\s+", "", name_text)
        duty = organization_marker + normalize_space(duty_text)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty_text.strip()
            or name in seen_names
        ):
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "副职列表链接；机构名前为姓名；完整链接文本为依据",
            }
        )
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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
