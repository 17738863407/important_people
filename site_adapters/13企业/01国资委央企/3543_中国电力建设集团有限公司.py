from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3543",
    "page_type": "人物列表完整页",
    "structure_group": "official_navigation_management_team_group_company",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "inline_parse_page",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "div.grid-group__list",
    "name_selector": ".grid-group__list__content h2",
    "duty_selector": ".grid-group__list__content p",
    "detail_link_selector": "",
    "target_column_name": "集团公司",
    "risk_flag": "官网当前集团公司管理团队页；只解析可见人物卡片中的姓名和职务",
    "confidence": "high",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析动态发现的集团公司管理团队页。"""
    soup = BeautifulSoup(html, "lxml")
    site_name = soup.select_one('meta[name="SiteName"]')
    column_name = soup.select_one('meta[name="ColumnName"]')
    actual_site_name = str(site_name.get("content", "")).strip() if site_name else ""
    actual_column_name = str(column_name.get("content", "")).strip() if column_name else ""
    if actual_site_name != str(page_rule["organization"]):
        raise RuntimeError(f"动态发现页机构元数据不一致：{actual_site_name or '空'}")
    if actual_column_name != str(page_rule["target_column_name"]):
        raise RuntimeError(f"动态发现页栏目不是目标集团公司：{actual_column_name or '空'}")

    rows: list[dict[str, str]] = []
    for card in soup.select(str(page_rule["leader_region_selector"])):
        if _is_hidden(card):
            continue
        name_node = card.select_one(str(page_rule["name_selector"]))
        duty_node = card.select_one(str(page_rule["duty_selector"]))
        if name_node is None or duty_node is None:
            continue
        name = _normalize_text(name_node.get_text(" ", strip=True))
        duty = " ".join(duty_node.get_text(" ", strip=True).split())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if not duty:
            continue
        rows.append({"name": name, "evidence": duty, "detail_url": ""})

    if not rows:
        raise RuntimeError("动态发现页未解析到可验证人物卡片")
    return rows


def main() -> None:
    """直接采集现行集团公司管理团队页并导出十三列结果。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
