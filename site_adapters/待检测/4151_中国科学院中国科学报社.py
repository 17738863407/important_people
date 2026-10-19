from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4151",
    "page_type": "leader_table_with_javascript_redirect",
    "load_mode": "static_html",
    "fetch_mode": "raw_http",
    "parser": "page_specific",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "confidence": "high",
    "risk_notes": "入口原始HTML含现任领导表格，同时含跳往媒体矩阵的脚本；必须解析原始响应，不能跟随脚本跳转。",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从入口原始HTML的现任领导表格提取职务和姓名。"""
    from bs4 import BeautifulSoup

    if not html:
        from crawler_core.fetcher import fetch_by_raw_requests

        html = fetch_by_raw_requests(str(rule["url"])).html
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".text-content-box")
    if region is None:
        raise RuntimeError("未找到现任领导正文区域")
    rows: list[dict] = []
    for table_row in region.select("table tr"):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        duty = " ".join(cells[0].get_text(" ", strip=True).split())
        name = "".join(cells[1].get_text(" ", strip=True).split())
        if duty and name:
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导表格未解析出姓名和职务")
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
