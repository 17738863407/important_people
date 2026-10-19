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


PAGE_RULE = {
    "rule_id": "0533",
    "domain": "www.fecc.agri.cn",
    "page_type": "人物列表完整页",
    "structure_group": "fecc_center_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_fecc_center_leaders_v1",
    "leader_region_selector": "#lm3 + .ej_lmbox .ej_ld",
    "name_selector": ".t1",
    "duty_selector": ".t2",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "", "include_selectors": ["#lm3 + .ej_lmbox .ej_ld"], "exclude_selectors": []},
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "姓名中存在不换行空格；入口锚点不得作为人物详情页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#lm3 + .ej_lmbox .ej_ld",
            "name_selector": ".t1",
            "duty_selector": ".t2",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "中心领导", "end_anchor": "", "include_selectors": ["#lm3 + .ej_lmbox .ej_ld"], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "当前HTTP响应已直接提供完整中心领导列表"},
        "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True},
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白，不改变原始语义。"""
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ").replace("\u2003", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按中心领导列表DOM原始顺序抽取姓名和原始职务。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=#lm3 + .ej_lmbox .ej_ld；name=.t1；duty=.t2"

    for item in soup.select("#lm3 + .ej_lmbox .ej_ld li"):
        name_node = item.select_one(".t1")
        duty_node = item.select_one(".t2")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
