from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2817", "page_type": "人物表格页", "structure_group": "shenyang_veterans_br_rows_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_veterans_br_rows_v2",
    "leader_region_selector": ".main-wrap1 table tr", "name_selector": "人物行右td第1个br文本段",
    "duty_selector": "人物行右td第2个br文本段", "detail_link_selector": "人物行左td a[href]",
    "detail_strategy": {"required": True, "mode": "list_dynamic"},
    "risk_flag": "右td第3段为职责分工，不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表格行顺序解析br分隔的姓名、原始职务和人物链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select(".main-wrap1 table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2 or "title" in (cells[0].get("class") or []):
            continue
        fields = [clean_text(value) for value in cells[1].stripped_strings if clean_text(value)]
        if len(fields) != 3:
            raise RuntimeError(f"人物行文本段数量异常：{len(fields)}")
        name, evidence = fields[:2]
        link = cells[0].select_one("a[href]")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or link is None:
            raise RuntimeError("人物行姓名、职务或详情链接异常")
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        if not detail_url or detail_url == final_url or name in seen_names:
            raise RuntimeError(f"人物详情链接异常或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导表格没有有效人物行")
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
