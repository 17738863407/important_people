from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3920",
    "page_type": "同页人物导航与详情标签",
    "structure_group": "zibo_government_data_id_tabs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内含全部人物内容",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zibo_government_nav_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.sk-nav.sk-nav-tree",
    "name_selector": "li.sk-nav-item dd[data-id] a.lingdao",
    "duty_selector": "li.sk-nav-item直属职务标题",
    "detail_link_selector": "none_same_page_javascript_tabs",
    "risk_flag": "人物以data-id切换同页详情，javascript链接不得写入详情页",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中为均匀展示而插入的空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按导航职务组与data-id人物项原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one("ul.sk-nav.sk-nav-tree")
    if region is None:
        raise RuntimeError("未定位到市政府领导导航树")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > li.sk-nav-item"):
        direct_title = group.find("a", recursive=False)
        duty = clean_text(direct_title.get_text(" ", strip=True) if direct_title else "")
        if not duty:
            continue
        for person in group.select("dl.sk-nav-child > dd[data-id]"):
            name_link = person.select_one("a.lingdao")
            name = clean_name(name_link.get_text(" ", strip=True) if name_link else "")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
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
                    "selector_summary": "ul.sk-nav直属职务组及dd[data-id]人物项",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导导航树未提取到有效人物")
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
