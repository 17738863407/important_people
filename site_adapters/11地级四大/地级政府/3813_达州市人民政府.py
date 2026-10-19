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
    "rule_id": "3813", "domain": "www.dazhou.gov.cn", "page_type": "分职务领导卡片",
    "load_mode": "浏览器渲染DOM", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct",
    "collector": "browser_dom", "parser": "page_inline_dazhou_government_v1",
    "leader_region_selector": ".leader_info_cent", "name_selector": ".leader_mayor_name, .leader_ViceMayor li p, .leader_secretary li p",
    "duty_selector": ".leader_post", "detail_link_selector": ".leader_mayor a[href], .leader_ViceMayor a[href], .leader_secretary a[href]",
    "content_scope": {"start_anchor": "政府领导", "end_anchor": "", "include_selectors": [".leader_info_cent"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "姓名及个别链接含排版空格，按卡片边界确定性清理", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def append_group(rows: list[dict[str, str]], group, name_selector: str, duty: str, base_url: str, parser: str) -> None:
    for link in group.select("a[href]"):
        name_node = link.select_one(name_selector)
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        href = re.sub(r"\s+", "", str(link.get("href", "")))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and href:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, href), "confidence": "high", "parser": parser})


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader_info_cent")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    configurations = ((".leader_mayor", ".leader_mayor_name", "市长"), (".leader_ViceMayor", "li p", "副市长"), (".leader_secretary", "li p", "秘书长"))
    for selector, name_selector, duty in configurations:
        group = region.select_one(selector)
        if group:
            append_group(rows, group, name_selector, duty, base_url, parser)
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
