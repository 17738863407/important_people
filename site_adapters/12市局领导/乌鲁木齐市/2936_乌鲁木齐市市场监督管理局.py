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
    "rule_id": "2936",
    "page_type": "人物表格页",
    "structure_group": "wulumuqi_market_supervision_three_column_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_market_supervision_three_column_table_v2",
    "leader_region_selector": "#NewsContent table",
    "name_selector": "人物行第二列",
    "duty_selector": "人物行第三列单位职务职级",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "表头姓名含排版空格，人物姓名可能含中间点且长度超过四字",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并单元格排版空白并清理中文标点两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    text = re.sub(r"\s*·\s*", "·", text)
    return re.sub(r"\s*([、，；：（）])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按三列表格行顺序解析姓名与单位职务职级列。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("#NewsContent table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")
    rows = tables[0].select("tr")
    if not rows:
        raise RuntimeError("领导表格没有行")
    header = [clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].select("th, td")]
    if header != ["序号", "姓 名", "单位职务职级"]:
        raise RuntimeError(f"领导表格表头异常：{header}")

    records: list[object] = []
    seen_names: set[str] = set()
    for row in rows[1:]:
        cells = row.select("td")
        if len(cells) != 3:
            raise RuntimeError(f"人物表格列数异常：{len(cells)}")
        name = clean_text(cells[1].get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(cells[2].get_text(" ", strip=True))
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
