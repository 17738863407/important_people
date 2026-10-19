from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def split_name_duty(text: str) -> tuple[str, str]:
    """依据卡片文字的明确职务边界拆分姓名和职务。"""
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,4}?)(?P<duty>副部长|部长)", clean_name(text))
    if not match:
        return "", ""
    return match.group("name"), match.group("duty")


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.idcpc.org.cn",
        "page_type": "人物列表完整页",
        "structure_group": "idcpc_minister_leader_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_combined_name_duty",
        "collector": "static_http",
        "parser": "page_idcpc_minister_leader_cards_v1",
        "leader_region_selector": ".minister_leader",
        "name_selector": ".col-type > a[href] .subLeader_name",
        "duty_selector": ".col-type > a[href] .subLeader_name",
        "detail_link_selector": ".col-type > a[href]",
        "content_scope": {
            "include_selectors": [".minister_leader"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "direct_card_link",
            "detail_link_selector": ".col-type > a[href]",
            "candidate_links": [],
        },
        "risk_flag": "verified_combined_name_duty_cards",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".minister_leader",
                "item_selector": ".col-type > a[href]",
                "name_duty_selector": ".subLeader_name",
                "detail_link_selector": ".col-type > a[href]",
            },
            "api": {"enabled": False, "reason": "静态HTML人物卡片已直接包含姓名、职务和独立详情链接"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片原始顺序提取姓名、职务与真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".minister_leader")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select(".col-type > a[href]"):
        text_node = link.select_one(".subLeader_name")
        if text_node is None:
            continue
        name, duty = split_name_duty(text_node.get_text(" ", strip=True))
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.minister_leader；item=.col-type>a；field=.subLeader_name",
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
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3550"
    main(rule_id_value)
