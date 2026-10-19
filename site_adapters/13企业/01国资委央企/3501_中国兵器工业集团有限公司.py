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
    "rule_id": "3501",
    "page_type": "人物列表完整页",
    "structure_group": "兵器工业集团领导分行表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NorincoLeaderTableParser_v2",
    "leader_region_selector": ".box1 table:has(img)",
    "name_selector": "tr:nth-of-type(2) td",
    "duty_selector": "tr:nth-of-type(3) td",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "各表按图片行、姓名行、职务行排列；空td为版面占位",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _cell_text(cell: object) -> str:
    parts = [_clean_text(text) for text in cell.stripped_strings]
    return "；".join(part for part in parts if part)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按每张领导表格的姓名行与职务行原始列序配对。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for table in soup.select(".box1 table:has(img)"):
        table_rows = table.select("tr")
        if len(table_rows) < 3:
            continue
        names = [
            re.sub(r"[\s\u3000\xa0]+", "", cell.get_text(" ", strip=True))
            for cell in table_rows[1].select("td")
            if cell.get_text(" ", strip=True)
        ]
        duties = [
            text
            for cell in table_rows[2].select("td")
            if (text := _cell_text(cell))
        ]
        for name, evidence in zip(names, duties, strict=False):
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
                continue
            if name in seen_names:
                continue
            seen_names.add(name)
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": (
                        ".box1 table:has(img)；第二行非空td姓名；第三行对应td职务"
                    ),
                }
            )
    if not records:
        raise RuntimeError("兵器工业集团领导表格未解析到人物记录")
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
