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
    "rule_id": "3806", "domain": "www.changdu.gov.cn", "page_type": "首位大卡加领导列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_changdu_government_v1",
    "leader_region_selector": ".zfxxgk_zfld_box", "name_selector": ".zx_right h3 a, .zfld_fzx li p a[title]",
    "duty_selector": ".zx_right .fg, .zfld_fzx li > p", "detail_link_selector": ".zx_right h3 a[href], .zfld_fzx li p a[href]",
    "content_scope": {"start_anchor": "市领导", "end_anchor": "", "include_selectors": [".zfxxgk_zfld_box"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "首位领导和其余列表结构不同，均从各自人物卡片内抽取原始职务", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def make_row(name: str, duty: str, detail_url: str, parser: str) -> dict[str, str]:
    return {"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": parser}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zfxxgk_zfld_box")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    first_link = region.select_one(".zx_right h3 a[href]")
    first_duty = region.select_one(".zx_right .fg")
    if first_link and first_duty:
        name = re.sub(r"\s+", "", clean_text(first_link.get_text(" ", strip=True)))
        duty = clean_text(first_duty.get_text(" ", strip=True))
        if name and duty:
            rows.append(make_row(name, duty, urljoin(base_url, str(first_link.get("href", ""))), parser))
    for item in region.select(".zfld_fzx li"):
        link = item.select_one("p a[title][href]")
        paragraphs = item.find_all("p", recursive=False)
        if not link or len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        duty = clean_text(paragraphs[1].get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append(make_row(name, duty, urljoin(base_url, str(link.get("href", ""))), parser))
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
