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


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除姓名字段中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受领导卡片姓名字段中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "about.gmw.cn",
        "page_type": "人物列表完整页",
        "structure_group": "gmw_daily_editorial_board_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "_fetch_mode_override": True,
        "extract_mode": "leader_card_name_duty_direct",
        "collector": "static_http",
        "parser": "page_gmw_daily_editorial_board_cards_v1",
        "leader_region_selector": ".boss",
        "name_selector": ".boss .items .name",
        "duty_selector": ".boss .items h2.tit",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "报社编委会",
            "end_anchor": "联系方式",
            "include_selectors": [".boss"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_link_selector": "",
            "candidate_links": [],
        },
        "risk_flag": "raw_http_required_to_avoid_unrelated_script_redirect",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".boss",
                "item_selector": ".items",
                "name_selector": ".name",
                "duty_selector": "h2.tit",
                "detail_link_selector": "",
            },
            "api": {"enabled": False, "reason": "静态HTML编委会卡片已直接包含姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """限定报社编委会区域并按卡片原始顺序抽取姓名和职务。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".boss")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select(".items"):
        name_node = item.select_one(".name")
        duty_node = item.select_one("h2.tit")
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = normalize_space(duty_node.get_text(" ", strip=True)).strip(" ：:，,。.")
        if not is_name(name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.boss；item=.items；fields=h2.tit+.name；detail=none",
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
    rule_id_value = "3560"
    main(rule_id_value)
