from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2839",
    "page_type": "人物目录详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": ".article-content .trs_editor_view",
    "person_paragraph_selector": "p",
    "risk_flag": "页面仅公布局领导分工而未逐人公布职务，禁止把分工推断为职务",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """核验正文是否同时公开当前领导姓名和可用职务依据。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到局领导分工正文")
    rows: list[dict] = []
    seen: set[str] = set()
    for paragraph in region.select(page_rule["person_paragraph_selector"]):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u3400-\u9fff·\s]{2,12}?)\s*同志(?:\s|，|,|$)", paragraph_text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": "",
            "evidence": "",
            "detail_url": "",
            "confidence": "medium",
            "parser": "page_inline_nanning_investment_leader_assignments_v1",
            "selector_summary": "region=.article-content .trs_editor_view；person=p以姓名同志开头；duty=页面未公布",
        })
    if rows:
        raise RuntimeError(
            "当前页面仅公开局领导姓名及主持、分管、协助事项，未公开可作为依据说明的现任职务字段"
        )
    raise RuntimeError("局领导分工正文未解析到可验证姓名")


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
