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
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受页面强结构姓名字段中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def extract_current_duty(profile_text: str) -> str:
    """从当前人物简介块中提取完整现任句并执行允许的基本清洗。"""
    normalized = normalize_space(profile_text)
    match = re.search(r"现任([^。]+)[。]?", normalized)
    if match is None:
        return ""
    return normalize_space(match.group(1)).strip(" ：:，,。.")


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.zysy.org.cn",
        "page_type": "图片下方第一行简介",
        "structure_group": "zysy_current_leader_profile_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_current_sentence",
        "collector": "static_http",
        "parser": "page_zysy_current_leader_profile_cards_v1",
        "leader_region_selector": ".layout-container .list",
        "name_selector": ".item > .img-wrap .name strong",
        "duty_selector": ".item > .txt-item .item-sele-item-1",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": [".layout-container .list"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "candidate_links": [],
        },
        "risk_flag": "verified_profile_cards_current_sentence_without_real_bio_links",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".layout-container .list",
                "item_selector": ":scope > .item",
                "name_selector": ":scope > .img-wrap .name strong",
                "profile_selector": ":scope > .txt-item .item-sele-item-1",
            },
            "api": {"enabled": False, "reason": "静态HTML人物卡片已直接包含姓名和完整现任句"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片原始顺序抽取姓名及卡片内完整现任句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".layout-container .list")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    parser = str(page_rule.get("parser", ""))
    for item in region.select(":scope > .item"):
        name_node = item.select_one(":scope > .img-wrap .name strong")
        profile_node = item.select_one(":scope > .txt-item .item-sele-item-1")
        if name_node is None or profile_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = extract_current_duty(profile_node.get_text(" ", strip=True))
        if not is_name(name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": parser,
                "selector_summary": "strategy=custom_parse_page；region=.layout-container .list；item=.item；fields=.name strong+.item-sele-item-1内现任句",
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
    rule_id_value = "3566"
    main(rule_id_value)
