from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3906",
    "page_type": "单页领导标签与内嵌详情",
    "structure_group": "yongzhou_government_left_nav_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "name_and_direct_text",
    "collector": "requests",
    "parser": "page_inline_yongzhou_government_nav_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.ldLeft",
    "name_selector": ":scope > li > span",
    "duty_selector": ":scope > li直属文本",
    "detail_link_selector": "",
    "risk_flag": "人物详情均内嵌同一页并用标签切换；右侧包含分工、简历和活动，不得把留言或活动链接作为详情页",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按左侧人物标签原始顺序提取姓名及直属职务文本。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到政府领导左侧人物标签列表")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for item in region.find_all("li", recursive=False):
        name_node = item.find("span", recursive=False)
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(" ".join(str(value) for value in item.find_all(string=True, recursive=False)))
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
                "selector_summary": "ul.ldLeft直属li内span姓名与直属职务文本",
            }
        )

    if not rows:
        raise RuntimeError("政府领导人物标签列表未提取到有效人物")
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
