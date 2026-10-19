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
    "rule_id": "3178",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_statistics_biography_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "div.view.TRS_UEDITOR.trs_web",
    "name_selector": ":scope > p",
    "risk_flag": "人物首段后紧随工作分工段，必须排除；正文存在汉字间排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从每个人物简介首段中提取姓名与完整现任句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in soup.select("div.view.TRS_UEDITOR.trs_web > p"):
        compact = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        match = re.match(
            r"^(?P<name>[一-鿿·]{2,4})[，,].*?(?P<evidence>现任[^。]*。)",
            compact,
        )
        if match is None:
            continue
        name = match.group("name")
        if name in seen_names:
            continue
        seen_names.add(name)
        evidence = match.group("evidence").removeprefix("现任").removesuffix("。").strip()
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_yinchuan_statistics_biography_paragraphs_v1",
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
