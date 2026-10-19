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
    "rule_id": "3810", "domain": "www.danzhou.gov.cn", "page_type": "领导卡片列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_danzhou_government_v1",
    "leader_region_selector": ".sjb-ldjs", "name_selector": ".sjb-ldjs-t-m a[title] p, .sjb-ldjs-t-m2 a[title] p",
    "duty_selector": ".sjb-ldjs-t-m a[title] p, .sjb-ldjs-t-m2 a[title] p", "detail_link_selector": ".sjb-ldjs-t-m a[title][href], .sjb-ldjs-t-m2 a[title][href]",
    "content_scope": {"start_anchor": "市政府领导", "end_anchor": "政府机构", "include_selectors": [".sjb-ldjs"], "exclude_selectors": [".lm1-m", ".lm6-m1", ".tongyonglb"]},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "领导列表与政府机构、动态同处大容器，仅取三个领导卡片区", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".sjb-ldjs")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for link in region.select(".sjb-ldjs-t-m li > a[title][href], .sjb-ldjs-t-m2 li > a[title][href]"):
        paragraphs = link.find_all("p", recursive=False)
        if len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", clean_text(paragraphs[0].get_text(" ", strip=True)))
        duty = clean_text(paragraphs[1].get_text(" ", strip=True))
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
