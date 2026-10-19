from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0839",
    "page_type": "人物列表完整页",
    "structure_group": "lasa_sasac_mixed_leader_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lasa_sasac_mixed_leader_groups_v1",
    "leader_region_selector": ".kp.lead, .kp.ldlist",
    "name_selector": ".kp.lead .info p.a span:first-child；.kp.ldlist li p:first-child",
    "duty_selector": ".kp.lead .info p.a span:nth-child(2)；.kp.ldlist li p:nth-child(2)或所属分组标题",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".kp.lead .info p.a a[href], .kp.ldlist li a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "one_list_item_repeats_name_in_duty_field_and_uses_group_heading",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "primary_cards": ".kp.lead .info p.a",
            "groups": ".kp.ldlist",
            "group_title": ".dh span",
            "group_items": "ul.detail li a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML直接包含人物卡片、分组标题和动态详情链接",
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
    """校验强结构字段并按页面顺序追加记录。"""
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
    """按主职卡片、随后分组列表的网页顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for heading in soup.select(".kp.lead .info p.a"):
        spans = heading.select("span")
        name_link = spans[0].select_one("a[href]") if len(spans) >= 2 else None
        duty_node = spans[1] if len(spans) >= 2 else None
        if name_link is None or duty_node is None:
            continue
        append_row(
            rows,
            seen_names,
            name_link.get_text(" ", strip=True),
            duty_node.get_text(" ", strip=True),
            heading.get_text(" ", strip=True),
            urljoin(final_url, str(name_link.get("href", "")).strip()),
            page_rule,
            "主职卡片.info p.a内分离姓名与职务节点",
        )

    for group in soup.select(".kp.ldlist"):
        title_node = group.select_one(".dh span")
        group_duty = normalize_space(title_node.get_text(" ", strip=True)) if title_node else ""
        for link in group.select("ul.detail li a[href]"):
            fields = link.select("p")
            if len(fields) < 2:
                continue
            name = normalize_space(fields[0].get_text(" ", strip=True))
            item_duty = normalize_space(fields[1].get_text(" ", strip=True))
            if item_duty == name:
                duty = group_duty
                evidence = group_duty
                summary = "分组列表第一p姓名；重复姓名字段时使用所属分组标题职务"
            else:
                duty = item_duty
                evidence = link.get_text(" ", strip=True)
                summary = "分组列表链接内第一、第二p姓名职务字段"
            append_row(
                rows,
                seen_names,
                name,
                duty,
                evidence,
                urljoin(final_url, str(link.get("href", "")).strip()),
                page_rule,
                summary,
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
