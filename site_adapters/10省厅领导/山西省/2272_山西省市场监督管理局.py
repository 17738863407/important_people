from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩表格排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导信息表格行顺序提取姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in soup.select("#zzjg .t_con table tr"):
        cells = table_row.select("th, td")
        if len(cells) != 2:
            continue
        name = re.sub(r"\s+", "", clean_text(cells[0].get_text(" ", strip=True)))
        evidence = clean_text(cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not re.search(r"书记|局长|党组|巡视员|纪检", evidence) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_market_supervision_table_v2",
                     "selector_summary": "leader=#zzjg .t_con table tr；name=cell1；duty=cell2；detail=none"})
    return rows


PAGE_RULE = {
    "rule_id": "2272", "page_type": "人物表格页", "structure_group": "shanxi_market_supervision_leader_table", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_market_supervision_table_v2",
    "leader_region_selector": "#zzjg .t_con table tr", "name_selector": "th:first-child, td:first-child", "duty_selector": "th:nth-child(2), td:nth-child(2)", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "信息更新于", "include_selectors": ["#zzjg .t_con"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "raw_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "同区域另有更新时间表格，只接受两列且第二列包含领导职务关键词的行", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#zzjg .t_con table tr", "name_selector": "th:first-child, td:first-child", "duty_selector": "th:nth-child(2), td:nth-child(2)", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "信息更新于", "include_selectors": ["#zzjg .t_con"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导表格已直出姓名和职务"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
