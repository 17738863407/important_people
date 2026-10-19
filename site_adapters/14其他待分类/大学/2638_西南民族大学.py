from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2638",
    "page_type": "多人物详情合并页",
    "structure_group": "swun_current_leaders_protected_page",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "grouped_duty_names",
    "collector": "browser_dom",
    "parser": "page_inline_swun_current_leaders_v2",
    "leader_region_selector": "div.adldlist.pc",
    "name_selector": ".adldlist-bd a[title]",
    "duty_selector": ".adldlist-hd",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["div.adldlist.pc"],
        "exclude_selectors": ["div.adldlist.sj"],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "页面受动态防护保护，使用项目独立Chrome CDP通道；PC版与移动版人物DOM重复，只解析PC版并按姓名合并多个职务分组",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """移除姓名和职务标签中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析PC版职务分组，按首次出现顺序合并同一人物的多项职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.adldlist.pc")
    if region is None:
        raise RuntimeError("未找到现任领导PC版区域 div.adldlist.pc")

    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for item in region.select(":scope > ul > li"):
        duty_node = item.select_one(":scope > .adldlist-hd")
        names_node = item.select_one(":scope > .adldlist-bd")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("：:")
        if not duty or names_node is None:
            continue
        for link in names_node.select(":scope > a[title]"):
            name = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                raise RuntimeError(f"现任领导姓名格式异常：{name or '<空>'}")
            existing = row_by_name.get(name)
            if existing is None:
                existing = {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": "page_inline_swun_current_leaders_v2",
                    "selector_summary": "div.adldlist.pc > ul > li；.adldlist-hd职务；.adldlist-bd a[title]姓名",
                }
                rows.append(existing)
                row_by_name[name] = existing
                continue
            duties = existing["evidence"].split("；")
            if duty not in duties:
                duties.append(duty)
                existing["duty"] = "；".join(duties)
                existing["evidence"] = existing["duty"]

    if not rows:
        raise RuntimeError("现任领导PC版区域未解析出有效人物")
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
