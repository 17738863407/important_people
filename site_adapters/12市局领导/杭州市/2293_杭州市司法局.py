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
    "rule_id": "2293",
    "page_type": "人物列表完整页",
    "structure_group": "hangzhou_justice_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_justice_leader_list_v1",
    "leader_region_selector": "li a[href]:has(.list_1):has(.list_2)",
    "name_selector": ".list_1",
    "duty_selector": ".list_2",
    "detail_link_selector": "同一人物项a[href]",
    "detail_strategy": {"required": False, "mode": "same_item_link", "same_host_only": True},
    "risk_flag": "页面含其他列表和正文，必须同时命中list_1姓名与list_2职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM原序解析同项姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    for anchor in soup.select("li a[href]:has(.list_1):has(.list_2)"):
        name = clean_text(anchor.select_one(".list_1").get_text(" ", strip=True))
        duty = clean_text(anchor.select_one(".list_2").get_text(" ", strip=True))
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
                "selector_summary": "领导li同一a内.list_1姓名、.list_2职务及href",
            }
        )
    if not records:
        raise ValueError("未在市司法局领导列表中解析到有效人物")
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
