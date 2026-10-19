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
    "rule_id": "2791", "page_type": "人物表格页", "structure_group": "wuhan_sports_person_table_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_sports_person_table_v2",
    "leader_region_selector": "正文唯一table", "name_selector": "tr第二td直属第一p开头姓名",
    "duty_selector": "tr第二td直属第一p姓名后的原始职务", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "同一单元格含分工和简历，必须只取直属第一p的姓名职务；文章即权威入口，无独立详情页；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    fields = [clean_text(row.select(":scope > td")[-1].select_one(":scope > p").get_text(" ", strip=True)) for row in soup.select("table tr") if len(row.select(":scope > td")) == 2 and row.select(":scope > td")[-1].select_one(":scope > p")]
    if fields and not any(re.match(r"^[\u3400-\u9fff·]{2,20}\s+\S+", field) for field in fields):
        try:
            soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); tables = soup.select("table")
    if len(tables) != 1:
        raise RuntimeError(f"人物表格数量异常：{len(tables)}")
    records: list[object] = []; seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.select(":scope > td")
        if len(cells) != 2:
            raise RuntimeError(f"人物表格行单元格数量异常：{len(cells)}")
        paragraphs = cells[1].select(":scope > p")
        if len(paragraphs) < 3:
            raise RuntimeError(f"人物信息段落数量异常：{len(paragraphs)}")
        heading = clean_text(paragraphs[0].get_text(" ", strip=True)); match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,20})\s+(?P<duty>.+)", heading)
        if match is None:
            raise RuntimeError(f"人物姓名职务首段格式异常：{heading}")
        name = match.group("name"); evidence = clean_text(match.group("duty"))
        if name in seen_names or not evidence:
            raise RuntimeError(f"人物姓名重复或职务为空：{name} {evidence}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("人物表格没有可验证记录")
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
