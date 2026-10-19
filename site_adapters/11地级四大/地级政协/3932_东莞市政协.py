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
    "rule_id": "3932",
    "domain": "dgzx.dg.gov.cn",
    "page_type": "选项卡人物字段列表",
    "structure_group": "dongguan_cppcc_leader_tabs_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_dongguan_cppcc_leader_tabs_v1",
    "leader_region_selector": ".list_con_r .js-bd",
    "name_selector": ".lb_tt_zxld dd p font",
    "duty_selector": ".lb_tt_zxld dd p font",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".list_con_r .js-bd"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导详情块由选项卡切换显示，需按字段标签配对并避免把简介、分工混入职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".list_con_r .js-bd",
            "item_selector": ":scope > .lb_tt",
            "field_selector": ".lb_tt_zxld dd > p",
        },
        "api": {"enabled": False, "reason": "当前静态HTML已含可回指的姓名和职务字段"},
    },
}


def normalize_text(value: str) -> str:
    """清理字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按官网选项卡原始顺序解析明确标注的姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".list_con_r .js-bd")
    if region is None:
        raise RuntimeError("未找到政协领导选项卡内容区 .list_con_r .js-bd")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in region.select(":scope > .lb_tt"):
        fields: dict[str, str] = {}
        for paragraph in card.select(".lb_tt_zxld dd > p"):
            label = normalize_text(paragraph.select_one("span").get_text(" ", strip=True)) if paragraph.select_one("span") else ""
            value_node = paragraph.select_one("font")
            value = normalize_text(value_node.get_text(" ", strip=True) if value_node else "")
            if label and value:
                fields[label] = value

        name = re.sub(r"[（(](?:女|男)[）)]$", "", fields.get("姓名", ""))
        duty = fields.get("职务", "").strip("。；; ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".list_con_r .js-bd>.lb_tt；按姓名/职务标签配对",
            }
        )
    if not rows:
        raise RuntimeError("政协领导内容区未解析出有效姓名和职务")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
