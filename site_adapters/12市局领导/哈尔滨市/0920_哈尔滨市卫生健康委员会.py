from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0920",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_name_duty_title_followed_by_work",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "独立人物职务标题段落段首",
    "duty_selector": "姓名后的标题职务文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "只解析以主任或组长结尾的独立标题段落，排除工作分工段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff](?:[ \u2000-\u200b]*[\u4e00-\u9fff]){1,2})"
        r"\s+(?P<duty>.+(?:主任|组长))$"
    )
    for paragraph in soup.select("#detailContent p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match:
            continue
        name = compact_text(match.group("name"))
        duty = compact_text(match.group("duty"))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "#detailContent独立人物职务标题段落",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物职务标题段落")
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
