from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_text(text: str) -> str:
    """清理网页排版空白，不改变字段语义。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", str(text or "")).strip()


def build_page_rule(rule_id: str) -> dict:
    """构造经当前在线页面核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.spp.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "spp_fontzoom_role_name_split_spans_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "role_name_split_spans",
        "collector": "static_http",
        "parser": "page_spp_fontzoom_role_name_split_spans_v1",
        "leader_region_selector": "#fontzoom",
        "name_selector": "#fontzoom p > span:nth-of-type(2)",
        "duty_selector": "#fontzoom p > span:nth-of-type(1)",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": ["#fontzoom"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_link_selector": "",
            "candidate_links": [],
        },
        "risk_flag": "verified_static_role_name_pairs_without_detail_links",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#fontzoom",
                "item_selector": "p:has(> span:nth-of-type(2))",
                "name_selector": "> span:nth-of-type(2)",
                "duty_selector": "> span:nth-of-type(1)",
            },
            "api": {"enabled": False, "reason": "静态HTML正文直接包含职务与姓名配对字段"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文中职务、姓名双 span 的原始顺序抽取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for paragraph in region.select("p"):
        spans = paragraph.find_all("span", recursive=False)
        if len(spans) != 2:
            continue
        duty = normalize_text(spans[0].get_text(" ", strip=True)).rstrip("：:")
        name = re.sub(r"\s+", "", normalize_text(spans[1].get_text(" ", strip=True)))
        pair = (name, duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty or pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#fontzoom；item=direct-child p；fields=two direct span nodes",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫，且不更新公共采集记忆。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        build_page_rule(rule_id),
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3585"
    main(rule_id_value)
