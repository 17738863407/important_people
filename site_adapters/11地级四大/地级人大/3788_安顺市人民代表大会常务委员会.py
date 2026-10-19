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
    "rule_id": "3788", "domain": "www.asrd.gov.cn", "page_type": "侧栏领导名单",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_anshun_people_congress_v1",
    "leader_region_selector": "#my_menu", "name_selector": "a[id^='am']",
    "duty_selector": "a[id^='am']", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导之窗", "end_anchor": "", "include_selectors": ["#my_menu"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "侧栏项目以职务全角冒号姓名排列，页面未提供可验证人物详情链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("#my_menu a[id^='am']"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([^：:]+)[：:]\s*(.+)", text)
        if not match:
            continue
        duty = clean_text(match.group(1))
        name = re.sub(r"\s+", "", clean_text(match.group(2)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
