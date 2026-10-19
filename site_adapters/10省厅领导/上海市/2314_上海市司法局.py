from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2314",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".trout-region-info .leader",
    "item_selector": ".trout-region-info .leader ul.picTextList > li",
    "risk_note": "每个人物卡片含标题和简介，姓名可能含全角空格，职务以简介中的完整现任原句为准。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩简介正文排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def compact_name(value: str) -> str:
    """移除姓名中的普通及全角排版空格。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物卡片顺序提取标题开头姓名和简介现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        title_node = item.select_one("p.title span")
        profile_node = item.select_one("p.date")
        if title_node is None or profile_node is None:
            continue
        raw_title = title_node.get_text(" ", strip=True)
        name_match = re.match(r"^([\u4e00-\u9fff·\u3000 ]{2,8}?)\s+.+$", raw_title)
        profile = clean_text(profile_node.get_text(" ", strip=True))
        duty_match = re.search(r"现任[^。]*。", profile)
        if not name_match or not duty_match:
            continue
        name = compact_name(name_match.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": duty_match.group(0).removeprefix("现任").removesuffix("。").replace("（挂职）", "").replace("(挂职)", ""),
                "detail_url": "",
            }
        )

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
