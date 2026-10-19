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
    "rule_id": "2420",
    "page_type": "人物表格页",
    "structure_group": "hangzhou_audit_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_audit_leader_table_v1",
    "leader_region_selector": "#ldbz_tab",
    "name_selector": "a.sjj_name[href]",
    "duty_selector": "同一行th.duties",
    "detail_link_selector": "a.sjj_name[href]",
    "detail_strategy": {"required": False, "mode": "same_row_link", "same_host_only": True},
    "risk_flag": "页面含布局表格，严格限定ldbz_tab领导表格及数据行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").replace("\u200d", "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导表格数据行原序解析职务、姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    for row in soup.select("#ldbz_tab tr"):
        duty_node = row.select_one("th.duties")
        anchor = row.select_one("a.sjj_name[href]")
        if duty_node is None or anchor is None:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True))
        name = clean_text(anchor.get_text(" ", strip=True))
        detail_url = urljoin(final_url, anchor.get("href", ""))
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
                "selector_summary": "#ldbz_tab数据行th.duties职务与a.sjj_name姓名链接",
            }
        )
    if not records:
        raise ValueError("未在市审计局领导表格中解析到有效人物")
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
