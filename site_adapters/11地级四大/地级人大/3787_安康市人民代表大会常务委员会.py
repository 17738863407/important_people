from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3787", "domain": "rd.ankang.gov.cn", "page_type": "常委会组成人员分组列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_inline_ankang_people_congress_v1", "leader_region_selector": ".right_list .cwh_1",
    "name_selector": "h2 + ul li a[href]", "duty_selector": "h2", "detail_link_selector": "h2 + ul li a[href]",
    "content_scope": {"start_anchor": "主任", "end_anchor": "", "include_selectors": [".right_list .cwh_1"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "页面为常委会组成人员，按主任、副主任、秘书长、常委会委员分组完整提取",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right_list .cwh_1")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    current_duty = ""
    for child in region.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h2":
            current_duty = clean_text(child.get_text(" ", strip=True))
            continue
        if child.name != "ul" or not current_duty:
            continue
        for link in child.select("li a[href]"):
            name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                rows.append({"name": name, "duty": current_duty, "evidence": current_duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
