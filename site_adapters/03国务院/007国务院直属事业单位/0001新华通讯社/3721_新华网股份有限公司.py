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
    "rule_id": "3721", "page_type": "公司领导多分组列表", "structure_group": "xinhuanet_company_leaders_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_xinhuanet_company_leaders_v1",
    "leader_region_selector": ".content.senior .senior-cont", "name_selector": ".executives-item .item-name, .senior-cont-boardOfficer .boardOfficer-name", "duty_selector": ".executives-item .item-post, .senior-cont-boardOfficer .boardOfficer-post", "detail_link_selector": "",
    "content_scope": {"start_anchor": "公司党委", "end_anchor": "关于我们", "include_selectors": [".content.senior .senior-cont"], "exclude_selectors": [".executives-layer", "script", "style"]}, "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含公司党委、董事、高级管理人员三组且同一人物跨组重复；弹层重复姓名职务和简历必须排除，多项职务须按首次出现顺序合并", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_multi_group_visible_cards",
    "locator": {"css": {"container_selector": ".content.senior .senior-cont", "row_selector": ".executives-item, .senior-cont-boardOfficer li"}, "api": {"enabled": False, "reason": "原始HTML已完整提供三个领导分组的可见姓名和职务"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def split_duties(value: str) -> list[str]:
    value = clean_text(value).replace("董事 副总裁", "董事；副总裁")
    return [item.strip() for item in re.split(r"[、，,；;]", value) if item.strip()]


def add_person(rows: list[dict[str, str]], positions: dict[str, int], name: str, duties: list[str], page_rule: dict) -> None:
    name = clean_text(name).replace(" ", "")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return
    if name not in positions:
        positions[name] = len(rows)
        rows.append({"name": name, "duty": "", "detail_url": "", "source_text": "", "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=three_leader_groups；order=first_dom_occurrence"})
    row = rows[positions[name]]
    existing = [item for item in row["duty"].split("；") if item]
    for duty in duties:
        if duty not in existing:
            existing.append(duty)
    row["duty"] = "；".join(existing)
    row["source_text"] = row["duty"]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".content.senior .senior-cont")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    positions: dict[str, int] = {}
    for block in container.select(".executives-item, .senior-cont-boardOfficer li"):
        if "executives-item" in (block.get("class") or []):
            name_node = block.select_one(".item-name")
            duty_nodes = block.select(".item-post")
        else:
            name_node = block.select_one(".boardOfficer-name")
            duty_nodes = block.select(".boardOfficer-post")
        if name_node is None:
            continue
        duties: list[str] = []
        for node in duty_nodes:
            for duty in split_duties(node.get_text(" ", strip=True)):
                if duty not in duties:
                    duties.append(duty)
        add_person(rows, positions, name_node.get_text(" ", strip=True), duties, page_rule)
    return [row for row in rows if row["duty"]]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
