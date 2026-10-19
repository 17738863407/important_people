from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3048",
    "page_type": "人物列表完整页",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "anhui_petition_leader_window_v3",
    "leader_region_selector": "div.ld_contain.clearfix",
    "name_selector": "a[title] .name",
    "duty_selector": "a[title] .positions",
    "detail_link_selector": "a[href*='content/column'][title]",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "online会跳转无障碍平台，raw_http保留权威入口原始领导列表",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白和姓名后的页面分隔冒号。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导之窗左侧名单DOM顺序动态解析，不使用固定人物结果。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        name_node = link.select_one(".name")
        duty_node = link.select_one(".positions")
        name = re.sub(r"[\s：:]+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, _clean_text(link.get("href")))
        if detail_url == final_url:
            detail_url = ""
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence=page_rule["confidence"],
                parser=page_rule["parser"],
            )
        )
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
