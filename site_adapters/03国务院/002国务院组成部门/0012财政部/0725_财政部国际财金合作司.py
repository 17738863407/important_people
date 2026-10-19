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
    "rule_id": "0725",
    "page_type": "人物列表完整页",
    "structure_group": "姓名职务排版段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofInternationalFinanceLeaderParagraphParser_v2",
    "leader_region_selector": ".TRS_Editor p",
    "risk_flag": "姓名内部可能含字距空白，应以段落最后一个连续空白串作为职务边界",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_field(value: str) -> str:
    """仅删除姓名或职务字段内部的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序，以最后一个空白串切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        raw_text = paragraph.get_text("", strip=False).strip(" \t\r\n\u00a0\u3000")
        gaps = list(re.finditer(r"[\s\u00a0\u3000]+", raw_text))
        if not gaps:
            continue
        boundary = gaps[-1]
        name = _compact_field(raw_text[: boundary.start()])
        duty = _compact_field(raw_text[boundary.end() :])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".TRS_Editor人物段落；最后空白串切分姓名与职务",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
