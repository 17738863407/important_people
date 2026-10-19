from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1351",
    "page_type": "人物表格页",
    "structure_group": "hangzhou_science_bureau_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_science_bureau_leader_table_v1",
    "leader_region_selector": "table.jgzn",
    "name_selector": "数据行第二列a[href]",
    "duty_selector": "数据行第一列",
    "detail_link_selector": "数据行第二列a[href]",
    "detail_strategy": {"required": False, "mode": "same_row_link", "same_host_only": True},
    "risk_flag": "页面还有导航表格，严格限定含职务姓名表头的jgzn人物表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导表格数据行原序解析职务、姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    for table in soup.select("table.jgzn"):
        header_text = [clean_text(cell.get_text(" ", strip=True)) for cell in table.select("tr:nth-of-type(2) td")]
        if header_text[:2] != ["职务", "姓名"]:
            continue
        for row in table.select("tr")[2:]:
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            duty = clean_text(cells[0].get_text(" ", strip=True))
            anchor = cells[1].select_one("a[href]")
            name = clean_text(anchor.get_text(" ", strip=True)) if anchor else ""
            detail_url = urljoin(final_url, anchor.get("href", "")) if anchor else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
                continue
            if urlparse(detail_url).netloc.lower() != host:
                detail_url = ""
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "selector_summary": "table.jgzn职务姓名表头；数据行第一列职务、第二列姓名链接",
                }
            )
    if not records:
        raise ValueError("未在市科技局职务姓名表格中解析到有效人物")
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
