from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1083",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": ".zhengwen",
    "risk_flag": "正文含主席、副主席、秘书长和常务委员四组，必须保持网页分组及表格原序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩正文中的普通、全角及排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_heading(value: object) -> str:
    """规范当前网页职务分组标题的空白和结尾冒号。"""
    return clean_text(value).rstrip("：:")


def add_row(rows: list[dict], seen: set[str], name: str, duty: str) -> None:
    """追加由当前分组标题与姓名节点共同确定的记录。"""
    normalized_name = clean_text(name)
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", normalized_name):
        return
    if normalized_name in seen:
        return
    seen.add(normalized_name)
    rows.append(
        {
            "name": normalized_name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "confidence": "high",
            "parser": "page_inline_hangzhou_cppcc_role_groups_v1",
            "selector_summary": (
                "region=.zhengwen；groups=主席/副主席/秘书长/常务委员"
            ),
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按网页顺序解析主席、副主席、秘书长和常务委员分组。"""
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        raise RuntimeError("未找到政协领导正文 .zhengwen")

    rows: list[dict] = []
    seen: set[str] = set()
    elements = [child for child in content.children if getattr(child, "name", None)]
    for index, element in enumerate(elements):
        heading = clean_heading(element.get_text(" ", strip=True))
        if heading == "主席":
            for next_element in elements[index + 1 :]:
                name = clean_text(next_element.get_text(" ", strip=True))
                if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
                    add_row(rows, seen, name, heading)
                    break
        elif heading == "副主席":
            table = next((item for item in elements[index + 1 :] if item.name == "table"), None)
            if table is None:
                raise RuntimeError("副主席标题后未找到名单表格")
            for cell in table.select("td"):
                add_row(rows, seen, cell.get_text(" ", strip=True), heading)
        elif heading == "秘书长":
            for next_element in elements[index + 1 :]:
                name = clean_text(next_element.get_text(" ", strip=True))
                if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
                    add_row(rows, seen, name, heading)
                    break
        elif heading.startswith("常务委员"):
            table = next((item for item in elements[index + 1 :] if item.name == "table"), None)
            if table is None:
                raise RuntimeError("常务委员标题后未找到名单表格")
            for cell in table.select("td"):
                add_row(rows, seen, cell.get_text(" ", strip=True), "常务委员")
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
