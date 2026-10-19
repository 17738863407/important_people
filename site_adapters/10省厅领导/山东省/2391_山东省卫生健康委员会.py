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
    """合并网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名与完整现任职务，排除基本信息。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".ldxx_con li"):
        name_node, duty_node = item.select_one(".ldxx_name"), item.select_one(".ldxx_zw")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        evidence = re.sub(r"^(?:现任职务|职务)\s*[：:]\s*", "", evidence)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence, "confidence": "high",
                     "parser": "page_inline_shandong_health_cards_v2", "selector_summary": "leader=.ldxx_con li；name=.ldxx_name；duty=.ldxx_zw；detail=none"})
    return rows


PAGE_RULE = {
    "rule_id": "2391", "page_type": "人物表格页", "structure_group": "shandong_department_ldxx_cards", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shandong_health_cards_v2",
    "leader_region_selector": ".ldxx_con li", "name_selector": ".ldxx_name", "duty_selector": ".ldxx_zw", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".ldxx_con"], "exclude_selectors": [".ldxx_jbxx"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "raw_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "同一卡片包含基本信息，必须只读取职务节点", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".ldxx_con li", "name_selector": ".ldxx_name", "duty_selector": ".ldxx_zw", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".ldxx_con"], "exclude_selectors": [".ldxx_jbxx"]}}, "api": {"enabled": False, "reason": "静态HTML领导卡片已直出姓名和职务"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
