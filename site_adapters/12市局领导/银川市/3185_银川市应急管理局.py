from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3185", "page_type": "人物列表完整页", "structure_group": "yinchuan_emergency_numbered_leaders_v2", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_yinchuan_emergency_numbered_leaders_v2",
    "leader_region_selector": ".zwxxgk_bd", "name_selector": "叶级编号段职务后的姓名", "duty_selector": "叶级编号段姓名前的职务", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zwxxgk_bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "页面以中文编号+职务+姓名连续文本列示；按明确职务边界最长优先切分，不使用姓名名单", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

LEADER_PATTERN = re.compile(
    r"^[一二三四五六七八九十]+、"
    r"(?P<duty>党委书记、局长|党委委员、副局长、三级调研员|党委委员、副局长|[一二三四]级调研员)"
    r"(?P<name>[\u4e00-\u9fff·]{2,4})。"
)


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """消除富文本将中文编号、职务和姓名拆成多节点产生的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按叶级编号段顺序和明确职务边界提取领导信息。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        if paragraph.select_one("p") is not None:
            continue
        match = LEADER_PATTERN.search(_clean_text(paragraph.get_text(" ", strip=True)))
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": ".zwxxgk_bd内叶级中文编号段；最长职务边界；末尾姓名"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
