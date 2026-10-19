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
    "rule_id": "1675",
    "page_type": "人物列表完整页",
    "structure_group": "科技部司局机构设置表格含括注",
    "reuse_scope": "most_department_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MostDepartmentProfileTableNoteParser_v2",
    "leader_region_selector": ".dept_profile table",
    "name_selector": "第二列按顿号分隔并剥离姓名后括注",
    "duty_selector": "第一列及第二列完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副司长单元格含挂职括注；姓名仅剥离括注，完整单元格原文必须保留为依据说明；页面无独立人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按机构设置表格顺序解析职务及含括注的同职务人员。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for table_row in soup.select(".dept_profile table tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        duty = _clean_text(cells[0].get_text(" ", strip=True)).rstrip(":：")
        names_text = _clean_text(cells[1].get_text(" ", strip=True))
        if not duty or "司长" not in duty:
            continue
        evidence = f"{duty}：{names_text}"
        for person_text in re.split(r"[、,，]", names_text):
            name = re.sub(r"[（(][^）)]*[）)]$", "", _clean_text(person_text))
            key = (name, duty)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": ".dept_profile table tr；首列职务；第二列按顿号拆分姓名并仅剥离姓名后括注",
                }
            )
    if not records:
        raise RuntimeError("机构设置表格未解析到二司领导记录")
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
