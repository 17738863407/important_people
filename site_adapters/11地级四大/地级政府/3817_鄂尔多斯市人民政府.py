from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3817", "domain": "www.ordos.gov.cn", "page_type": "人物标签领导列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_ordos_government_v1",
    "leader_region_selector": ".tabs5", "name_selector": ".tabs5 a[href] .swld_name", "duty_selector": ".tabs5 a[href] .swld_job",
    "detail_link_selector": ".tabs5 a[href]", "content_scope": {"start_anchor": "领导成员", "end_anchor": "分管工作", "include_selectors": [".tabs5"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "页面下方含活动新闻姓名，只取领导成员导航标签", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".tabs5")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for link in region.select(":scope > a[href]"):
        name_node = link.select_one(".swld_name")
        duty_node = link.select_one(".swld_job")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
