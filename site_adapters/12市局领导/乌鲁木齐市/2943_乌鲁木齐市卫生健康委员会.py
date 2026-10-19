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
    "rule_id": "2943",
    "page_type": "人物表格页",
    "structure_group": "wulumuqi_health_table_with_blank_rows_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_health_table_with_blank_rows_v2",
    "leader_region_selector": "#NewsContent table",
    "name_selector": "正式表头后非空人物行第二列",
    "duty_selector": "正式表头后非空人物行第三列单位职务、职级",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "表格正式表头之前和人物行之后均有空行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并表格单元格排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """定位正式表头后按行顺序解析非空人物三列表。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("#NewsContent table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")
    rows = tables[0].select("tr")
    expected_header = ["序号", "姓名", "单位职务、职级"]
    header_indexes = [
        index
        for index, row in enumerate(rows)
        if [clean_text(cell.get_text(" ", strip=True)) for cell in row.select("th, td")] == expected_header
    ]
    if len(header_indexes) != 1:
        raise RuntimeError(f"领导表格正式表头数量异常：{len(header_indexes)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for row in rows[header_indexes[0] + 1 :]:
        cells = row.select("td")
        values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if not any(values):
            continue
        if len(cells) != 3:
            raise RuntimeError(f"人物表格列数异常：{len(cells)}")
        name = values[1].replace(" ", "")
        evidence = values[2]
        evidence = re.sub(r"[（(](?:兼|挂职)[）)]", "", evidence).strip("，、； ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise RuntimeError(f"表格姓名结构异常：{name}")
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if row.select_one("a[href]") is not None:
            raise RuntimeError(f"人物行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导表格没有可验证人物行")
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
