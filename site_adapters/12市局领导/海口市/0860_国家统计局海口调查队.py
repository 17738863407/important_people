from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0860",
    "page_type": "人物表格页",
    "structure_group": "haikou_numbered_duty_name_headings",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".TRS_UEDITOR p",
    "name_selector": "编号标题职务结尾词后的姓名",
    "duty_selector": "编号后至姓名前职务文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "一、",
        "end_anchor": "领导协调工作机制",
        "include_selectors": [".TRS_UEDITOR p"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "以中文编号及队长或组长职务结尾词拆分标题，排除分工与AB角说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^[一二三四五六七八九十]+、\s*"
        r"(?P<duty>.+?(?:队长|组长))\s*(?P<name>[\u4e00-\u9fff]{2,4})$"
    )
    for paragraph in soup.select(".TRS_UEDITOR p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match:
            continue
        duty = clean_text(match.group("duty"))
        rows.append(
            {
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".TRS_UEDITOR中文编号职务姓名标题段落",
            }
        )
    if not rows:
        raise ValueError("领导分工正文未发现可验证的编号职务姓名标题")
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
