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
    "rule_id": "2208", "page_type": "人物表格页", "structure_group": "shenyang_hrss_two_field_table_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_hrss_two_field_table_v2",
    "leader_region_selector": "唯一table中表头后的tr", "name_selector": "人物行右td第一个非空文本段",
    "duty_selector": "人物行右td第二个非空文本段", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "右单元格第三段起为职责分工；只读取前两个字段，页面没有人物详情链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表格行顺序提取姓名与独立原始职务段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table")
    if len(tables) != 1:
        raise RuntimeError(f"人物表格命中数量异常：{len(tables)}")
    rows = tables[0].select("tr")
    if len(rows) < 2:
        raise RuntimeError("人物表格没有数据行")
    records: list[object] = []
    seen_names: set[str] = set()
    for row in rows[1:]:
        cells = row.select("td")
        if len(cells) != 2:
            raise RuntimeError("人物表格数据行列数异常")
        fields = [clean_text(value) for value in cells[1].stripped_strings if clean_text(value)]
        if len(fields) < 2:
            raise RuntimeError("人物表格缺少姓名或职务文本段")
        name = re.sub(r"\s+", "", fields[0])
        evidence = fields[1]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物表格姓名或职务字段异常")
        if name in seen_names:
            raise RuntimeError(f"人物表格姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
