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
    "rule_id": "3505",
    "page_type": "人物表格页",
    "structure_group": "国家电网头像行与职务姓名行表格",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "custom",
    "collector": "chrome_cdp",
    "parser": "SgccImageLeaderTableParser_v2",
    "leader_region_selector": ".article .content table",
    "name_selector": "img[alt]",
    "duty_selector": "下一行同列td",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTTP返回412且Playwright短页；Chrome CDP可稳定取得两张领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按每个头像行及其下一行同列单元格提取人物与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for table in soup.select(".article .content table"):
        table_rows = table.select("tr")
        for row_index, image_row in enumerate(table_rows[:-1]):
            image_cells = image_row.select("td")
            if not any(cell.select_one("img[alt]") for cell in image_cells):
                continue
            duty_cells = table_rows[row_index + 1].select("td")
            for cell_index, image_cell in enumerate(image_cells):
                image = image_cell.select_one("img[alt]")
                if image is None or cell_index >= len(duty_cells):
                    continue
                name = re.sub(r"\s+", "", (image.get("alt") or "").strip())
                full_text = _clean_text(duty_cells[cell_index].get_text(" ", strip=True))
                evidence = re.sub(rf"\s*{re.escape(name)}\s*$", "", full_text).strip()
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
                            ".article .content table；img[alt]姓名；下一行同列td职务"
                        ),
                    }
                )
    if not records:
        raise RuntimeError("国家电网领导表格未解析到人物记录")
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
