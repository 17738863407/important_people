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
    """删除强结构姓名字段中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def clean_chinese_duty(text: str) -> str:
    """按节点内明确的中英文边界保留中文职务，并删除中文词内排版空格。"""
    value = normalize_space(text)
    english_start = re.search(r"[A-Za-z]", value)
    chinese_part = value[: english_start.start()] if english_start else value
    return re.sub(r"\s+", "", chinese_part).strip(" ：:，,。.")


def is_name(text: str) -> bool:
    """仅接受强结构姓名节点中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u3400-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.celap.org.cn",
        "page_type": "人物列表完整页",
        "structure_group": "celap_leader_direct_and_grouped_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_direct_cards_and_grouped_names",
        "collector": "static_http",
        "parser": "page_celap_leader_mixed_cards_v1",
        "leader_region_selector": ".bt-rig-cen",
        "name_selector": ".ldname, .ld_bottom > div",
        "duty_selector": ".ld_zw, .yztop",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "现任领导",
            "include_selectors": [".bt-rig-cen"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "verified_mixed_direct_and_grouped_bilingual_leader_list",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".bt-rig-cen",
                "section_selector": ":scope > .yz",
                "direct_duty_selector": ".ld_zw",
                "direct_name_selector": ".ldname",
                "group_duty_selector": ".yztop",
                "group_name_selector": ".ld_bottom > div",
            },
            "api": {"enabled": False, "reason": "静态HTML人物区已直接包含姓名和职务"},
        },
    }


def append_row(
    rows: list[dict[str, str]],
    seen_names: set[str],
    name_text: str,
    duty_text: str,
    parser: str,
) -> None:
    """按页面顺序追加一条强结构人物记录。"""
    name = clean_name(name_text)
    duty = clean_chinese_duty(duty_text)
    if not is_name(name) or not duty or name in seen_names:
        return
    seen_names.add(name)
    rows.append(
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": parser,
            "selector_summary": (
                "strategy=custom_parse_page；region=.bt-rig-cen；"
                "direct=.ld_zw+.ldname；group=.yztop+.ld_bottom>div；detail=none"
            ),
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导分区的原始 DOM 顺序解析独立卡片和多人职务分组。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".bt-rig-cen")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    parser = str(page_rule.get("parser", ""))
    for section in region.select(":scope > .yz"):
        direct_duty = section.select_one(".ld_zw")
        direct_name = section.select_one(".ldname")
        if direct_duty is not None and direct_name is not None:
            append_row(
                rows,
                seen_names,
                direct_name.get_text(" ", strip=True),
                direct_duty.get_text(" ", strip=True),
                parser,
            )
            continue

        group_duty = section.select_one(".yztop")
        if group_duty is None:
            continue
        duty_text = group_duty.get_text(" ", strip=True)
        for name_node in section.select(".ld_bottom > div"):
            append_row(rows, seen_names, name_node.get_text(" ", strip=True), duty_text, parser)
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
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
    rule_id_value = "3563"
    main(rule_id_value)
