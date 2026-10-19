from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅提取惠州市人民政府表格，排除同页其他机构。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = next((table for table in soup.select("table.ld_list") if "惠州市人民政府" in table.get_text(" ", strip=True)), None)
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for tr in region.select("tr.ld_list_item"):
        cells = tr.find_all("td", recursive=False)
        duty = clean_text(cells[0].get_text(" ", strip=True)).replace(" ", "").rstrip("：:") if cells else ""
        if not duty:
            continue
        for link in tr.select("td a[href]"):
            name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source_url, str(link.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_huizhou_government_table_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3832", "page_type": "同页多机构表格", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_huizhou_government_table_v1", "leader_region_selector": "table.ld_list",
    "name_selector": "tr.ld_list_item td a", "duty_selector": "tr.ld_list_item td:first-child",
    "detail_link_selector": "tr.ld_list_item a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "同页存在市委、人大、政协、纪委表格，已以机构标题严格限定", "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
