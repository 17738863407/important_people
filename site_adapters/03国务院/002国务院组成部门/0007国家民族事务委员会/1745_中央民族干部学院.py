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
    "rule_id": "1745",
    "page_type": "人物表格页",
    "structure_group": "现任领导两列表格职务姓名",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CentralEthnicCadreCollegeLeaderTableParser_v2",
    "leader_region_selector": "#Content .p3 table",
    "name_selector": "td:nth-of-type(2) b:first-of-type",
    "duty_selector": "td:nth-of-type(1)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "院长姓名单元格还含其外部任职说明，仅取首个b姓名；页面无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按现任领导表格DOM行序抽取职务单元格和姓名粗体字段。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#Content .p3 table")
    if table is None:
        raise RuntimeError("未找到现任领导表格 #Content .p3 table")

    rows: list[dict] = []
    for table_row in table.select("tr"):
        cells = table_row.select("td")
        if len(cells) < 2:
            continue
        duty = _clean_text(cells[0].get_text(" ", strip=True))
        name_node = cells[1].select_one("b")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#Content .p3 table tr；td[1]职务；td[2]首个b姓名",
            }
        )

    if not rows:
        raise RuntimeError("现任领导表格未解析到职务姓名记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
