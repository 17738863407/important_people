from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1347",
    "page_type": "人物表格页",
    "structure_group": "sz_port_office_leader_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "sz_port_office_leader_table_v2",
    "leader_region_selector": ".article-content table",
    "name_selector": ".article-content table姓名列",
    "duty_selector": ".article-content table职务列",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文可能含其他表格，须以姓名、职务表头精确识别领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文领导表格原始行顺序提取姓名和职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    matched_tables = 0
    for table in soup.select(page_rule["leader_region_selector"]):
        rows = table.select("tr")
        if not rows:
            continue
        headers = [re.sub(r"\s+", "", clean_text(cell.get_text(" ", strip=True))) for cell in rows[0].find_all(["th", "td"], recursive=False)]
        if headers[:2] != ["姓名", "职务"]:
            continue
        matched_tables += 1
        for row in rows[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            name = re.sub(r"\s+", "", clean_text(cells[0].get_text(" ", strip=True)))
            evidence = clean_text(cells[1].get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
                raise RuntimeError("领导表格姓名或职务单元格异常")
            if name in seen_names:
                raise RuntimeError(f"领导表格姓名重复：{name}")
            seen_names.add(name)
            records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if matched_tables != 1 or not records:
        raise RuntimeError("未唯一定位姓名、职务领导表格或结果为空")
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
