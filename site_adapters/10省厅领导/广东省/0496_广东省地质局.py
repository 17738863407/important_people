from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "0496",
    "page_type": "人物列表完整页",
    "structure_group": "gd_geology_leader_division_article",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_gd_gkml_leader_division_v1",
    "leader_region_selector": ".article-content",
    "name_selector": ".article-content p",
    "duty_selector": ".article-content p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "官网当前领导分工文章；姓名和职务位于article-content直接段落",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析官方领导分工文章中的姓名和原始职务段落。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for para in soup.select(".article-content p"):
        text = re.sub(r"[\s\u3000\xa0]+", "", para.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff]{2,4})(?P<duty>省地质局.+)", text)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if not duty:
            continue
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_gd_gkml_leader_division_v1",
            }
        )

    return rows


def main() -> None:
    """直接采集并解析官网当前领导分工文章。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
