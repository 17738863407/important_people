from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3789", "domain": "www.baiyin.gov.cn", "page_type": "同页多机构分组领导列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_baiyin_people_congress_v1",
    "leader_region_selector": ".ldConList", "name_selector": ".ldConLtop h1, .ldConR li a",
    "duty_selector": ".ldConLtop h2, .ldConR > h1", "detail_link_selector": ".ldConLtop a[href], .ldConR li a[href]",
    "content_scope": {"start_anchor": "白银市人大常委会", "end_anchor": "白银市政府", "include_selectors": [".ldConList"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同页另有市委、政府、政协分组，只取第二个人大分组", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(".ldConList")
    if len(regions) < 2:
        return []
    region = regions[1]
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    primary_name = region.select_one(".ldConLtop h1")
    primary_duty = region.select_one(".ldConLtop h2")
    primary_link = region.select_one(".ldConLtop a[href]")
    if primary_name and primary_duty:
        name = re.sub(r"\s+", "", clean_text(primary_name.get_text(" ", strip=True)))
        duty = clean_text(primary_duty.get_text(" ", strip=True))
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(primary_link.get("href", ""))) if primary_link else "", "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    right = region.select_one(".ldConR")
    current_duty = ""
    if right:
        for child in right.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "h1":
                current_duty = clean_text(child.get_text(" ", strip=True))
            elif child.name == "ul" and current_duty:
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
