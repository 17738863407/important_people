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
    "rule_id": "1886",
    "page_type": "职务分组名单页",
    "structure_group": "neea_current_leaders_duty_name_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "#CurrentlyText",
    "name_selector": ":scope > p",
    "risk_flag": "首段内部包含旧领导HTML注释，只能读取当前可见文本节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析现任领导区域中可见的职务—姓名直属段落。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("#CurrentlyText > p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>[^：:]+)[：:](?P<name>[一-鿿·]{2,4})",
            evidence,
        )
        if match is None:
            continue
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": match.group("name"),
                "duty": match.group("duty"),
                "evidence": match.group("duty"),
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_neea_current_leaders_duty_name_paragraphs_v1",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
