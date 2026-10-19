from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1251",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".tab-content",
    "item_selector": ".tab-content .tab-pane",
    "risk_note": "人物tab内含工作动态链接，详情页不得使用当前页锚点或新闻链接。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩简介正文中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物tab顺序提取姓名和完整“现任”原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for pane in soup.select(page_rule["item_selector"]):
        paragraph = pane.select_one("p.text-2indent")
        if paragraph is None:
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"([\u4e00-\u9fff·]{2,8})，", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if not name_match or not duty_match:
            continue
        evidence = duty_match.group(0).removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name_match.group(1),
                "duty": "",
                "evidence": evidence,
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
