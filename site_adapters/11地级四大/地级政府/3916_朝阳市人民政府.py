from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3916",
    "page_type": "同页人物切换标签",
    "structure_group": "chaoyang_government_tabs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内含全部标签内容",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_chaoyang_government_tabs_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".lingdao-navld",
    "name_selector": "a.nav > .name",
    "duty_selector": "a.nav > .zhw",
    "detail_link_selector": "none_same_page_javascript_tabs",
    "risk_flag": "链接均为javascript同页标签；详情页链接必须留空",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """清理页面把nbsp写成普通文本的排版空白。"""
    text = str(value or "").replace("&nbsp", " ")
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", text).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按同页人物标签DOM顺序读取姓名与职务字段。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".lingdao-navld")
    if region is None:
        raise RuntimeError("未定位到市政府领导切换标签")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for tab in region.select(":scope > a.nav"):
        name_node = tab.select_one(":scope > .name")
        duty_node = tab.select_one(":scope > .zhw")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".lingdao-navld直属a.nav内.name与.zhw",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导切换标签未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
