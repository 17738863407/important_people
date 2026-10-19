from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0486",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_data_leader_card_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_static_http",
    "parser": "page_nanning_data_leader_card_v2",
    "leader_region_selector": ".sub_right .ldjsList > li",
    "name_selector": ".ldjsImg h4",
    "duty_selector": ".ldjsText p职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "卡片同时含职务和工作分工，必须只取明确职务字段节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".sub_right .ldjsList > li", "name_selector": ".ldjsImg h4", "duty_selector": ".ldjsText p"},
        "api": {"enabled": False, "reason": "领导卡片及姓名、职务字段均由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理字段节点中的排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取姓名和明确标注的原始职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".sub_right .ldjsList > li"):
        name_node = item.select_one(".ldjsImg h4")
        if name_node is None:
            continue
        duty_node = next(
            (
                node
                for node in item.select(".ldjsText p")
                if re.match(r"^职\s*务\s*[：:]", normalize_layout(node.get_text(" ", strip=True)))
            ),
            None,
        )
        if duty_node is None:
            continue
        name = re.sub(r"\s+", "", normalize_layout(name_node.get_text(" ", strip=True)))
        raw_duty = normalize_layout(duty_node.get_text(" ", strip=True))
        evidence = re.sub(r"^职\s*务\s*[：:]\s*", "", raw_duty)
        evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".sub_right .ldjsList > li按DOM顺序；.ldjsImg h4姓名；.ldjsText p中明确职务字段原文；排除工作分工",
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
