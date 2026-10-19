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
    "rule_id": "1676",
    "page_type": "人物列表完整页",
    "structure_group": "科技部司局机构设置表格",
    "reuse_scope": "most_department_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MostDepartmentProfileTableParser_v2",
    "leader_region_selector": ".dept_profile table",
    "name_selector": "第二列按顿号分隔",
    "duty_selector": "第一列",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页含下设处室与工作动态，且机构名称含港澳台办公室；必须限定.dept_profile领导表格，不得混入处室名或新闻人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按机构设置表格顺序解析职务及同职务人员。"""
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
        for name in re.split(r"[、,，]", names_text):
            name = _clean_text(name)
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
                    "selector_summary": ".dept_profile table tr；首列职务；第二列按顿号拆分姓名",
                }
            )
    if not records:
        raise RuntimeError("机构设置表格未解析到国际合作司领导记录")
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
