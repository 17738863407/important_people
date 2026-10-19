from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0082",
    "page_type": "人物表格页",
    "structure_group": "haikou_two_cell_leader_biography_rows",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "包含姓名职务与现任简历的两列表格行",
    "name_selector": "第一列段首姓名",
    "duty_selector": "第一列姓名后的完整职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "相关附件",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "页面含多层嵌套元数据表，仅解析第二列含现任简历的两列人物行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for table_row in soup.select("tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        if len(cells) != 2:
            continue
        title = clean_text(cells[0].get_text(" ", strip=True))
        biography = clean_text(cells[1].get_text(" ", strip=True))
        if "现任" not in biography:
            continue
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)", title)
        if not match:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty")).rstrip("。")
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "第二列含现任简历的两列表格行第一列姓名职务",
            }
        )
    if not rows:
        raise ValueError("领导信息表未发现可验证的两列人物行")
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
