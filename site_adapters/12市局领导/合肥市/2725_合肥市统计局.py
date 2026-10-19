from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩页面字段中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析领导分工正文中与分工段落交替出现的职务姓名行。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoom")
    if region is None:
        raise ValueError("未找到领导分工正文 #zoom")

    source_url = str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for paragraph in region.select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[一-鿿·]{2,6})", text)
        if not match:
            continue
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": match.group("name"),
                "duty": match.group("duty"),
                "detail_url": "",
                "evidence": match.group("duty"),
                "confidence": "high",
                "parser": "page_inline_hefei_statistics_role_name_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2725",
    "page_type": "多人物详情合并页",
    "structure_group": "hefei_statistics_role_name_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "multi_person_article",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_statistics_role_name_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "普通 HTTP 受 JavaScript 挑战；正文职务姓名行与分工段落交替",
    "confidence": "high",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
