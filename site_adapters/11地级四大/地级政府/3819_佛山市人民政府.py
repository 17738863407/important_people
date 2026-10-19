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
    "rule_id": "3819", "domain": "www.foshan.gov.cn", "page_type": "首位简介加副市长名单",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_foshan_government_v1",
    "leader_region_selector": ".zwgk-leader", "name_selector": ".introduce .sz a[href], .row-wrapper li a[href]",
    "duty_selector": ".introduce .jj .text, .row-wrapper .key", "detail_link_selector": ".introduce .sz a[href], .row-wrapper li a[href]",
    "content_scope": {"start_anchor": "市政府领导", "end_anchor": "政府信息公开", "include_selectors": [".zwgk-leader"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "市长职务取当前简介现任句，副市长取明确分组标题", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ").replace("\u200b", "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zwgk-leader")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    mayor_link = region.select_one(".introduce .sz a[href]")
    profile = region.select_one(".introduce .jj .text")
    if mayor_link and profile:
        name = re.sub(r"\s+", "", clean_text(mayor_link.get_text(" ", strip=True)))
        match = re.search(r"现任([^。]+)", clean_text(profile.get_text(" ", strip=True)))
        duty = clean_text(match.group(1)).rstrip("。") if match else ""
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(mayor_link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    for link in region.select(".row-wrapper li a[href]"):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            rows.append({"name": name, "duty": "副市长", "evidence": "副市长", "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
