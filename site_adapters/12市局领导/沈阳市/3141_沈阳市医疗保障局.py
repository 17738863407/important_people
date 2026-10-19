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
    "rule_id": "3141", "page_type": "人物表格页", "structure_group": "shenyang_medical_security_rows_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_medical_security_rows_v2",
    "leader_region_selector": ".view table tr", "name_selector": "人物行第2列开头姓名",
    "duty_selector": "姓名后至职责分工标签", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职责、办公地址和办公时间不得混入原始职务；不得向职务补加机构名",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导表格行顺序解析职责分工标签之前的姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select(".view table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != 2:
            continue
        text = clean_text(cells[1].get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u3400-\u9fff·]{2,10})\s+(?P<duty>.+?)\s+职责分工\s*[:：]", text)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("duty"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if row.select_one("a[href]") is not None:
            raise RuntimeError(f"人物行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
