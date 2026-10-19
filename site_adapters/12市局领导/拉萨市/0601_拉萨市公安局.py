from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0601",
    "page_type": "人物列表完整页",
    "structure_group": "lasa_police_mixed_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lasa_police_mixed_leader_cards_v1",
    "leader_region_selector": ".ldxx_item",
    "name_selector": ".kp.lead .info .a span:first-child；.ldlist li a p:first-of-type",
    "duty_selector": ".kp.lead .info .a span:nth-child(2)；.ldlist li a p:nth-of-type(2)",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".kp.lead .info .a a[href], .ldlist li a[href]",
        "max_detail_links": 30,
    },
    "risk_flag": "empty_primary_card_template_before_visible_leader",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "region": ".ldxx_item",
            "primary_cards": ".kp.lead .info .a",
            "deputy_items": ".ldlist ul.detail li a[href]",
            "deputy_fields": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML直接包含分离的姓名、职务节点和人物链接",
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


def append_row(
    rows: list[dict[str, str]],
    seen_names: set[str],
    name: str,
    duty: str,
    evidence: str,
    detail_url: str,
    page_rule: dict,
    selector_summary: str,
) -> None:
    """校验强结构字段并按页面顺序追加一条人物记录。"""
    clean_name = re.sub(r"\s+", "", normalize_space(name))
    clean_duty = normalize_space(duty)
    if (
        not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", clean_name)
        or not clean_duty
        or clean_name in seen_names
    ):
        return
    seen_names.add(clean_name)
    rows.append(
        {
            "name": clean_name,
            "duty": clean_duty,
            "evidence": clean_duty,
            "detail_url": detail_url,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按有效主职卡片、随后副职列表的网页顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ldxx_item")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for heading in region.select(".kp.lead .info .a"):
        spans = heading.select("span")
        name_link = spans[0].select_one("a[href]") if len(spans) >= 2 else None
        duty_node = spans[1] if len(spans) >= 2 else None
        if name_link is None or duty_node is None:
            continue
        detail_url = urljoin(final_url, str(name_link.get("href", "")).strip())
        append_row(
            rows,
            seen_names,
            name_link.get_text(" ", strip=True),
            duty_node.get_text(" ", strip=True),
            heading.get_text(" ", strip=True),
            detail_url,
            page_rule,
            "有效主职卡片.info .a内分离姓名与职务节点",
        )

    for link in region.select(".ldlist ul.detail li a[href]"):
        fields = link.select("p")
        if len(fields) < 2:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        append_row(
            rows,
            seen_names,
            fields[0].get_text(" ", strip=True),
            fields[1].get_text(" ", strip=True),
            link.get_text(" ", strip=True),
            detail_url,
            page_rule,
            "副职列表链接内第一、第二p姓名职务字段",
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
