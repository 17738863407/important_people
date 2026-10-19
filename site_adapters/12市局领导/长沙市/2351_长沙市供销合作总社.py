from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2351", "page_type": "人物列表完整页", "structure_group": "changsha_supply_cooperative_two_page_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "paginated_card_list", "collector": "static_http", "parser": "page_inline_changsha_supply_cooperative_two_page_cards_v1",
    "leader_region_selector": ".qqGrade_Right_06-01", "name_selector": ".qqGrade_Right_06-01b01姓名标签值", "duty_selector": ".qqGrade_Right_06-01b01职务标签值", "detail_link_selector": ".qqGrade_Right_06-01 a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".qqGrade_Right_06-01"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "card_link_only", "detail_collector_type": "static_http", "detail_link_selector": ".qqGrade_Right_06-01 a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "GB18030两页卡片目录；第二页必须在线获取，不使用或写入本地快照", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_two_page_card_label_values",
    "locator": {"css": {"leader_region_selector": ".qqGrade_Right_06-01", "name_selector": "card_name_label_value", "duty_selector": "card_duty_label_value", "detail_link_selector": "same_card_anchor_href"}, "api": {"enabled": False, "reason": "两页原始HTML卡片直接提供姓名、职务和详情链接"}, "migration": {"source": "legacy_local_page_two_cache_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def normalize_entry_html(html: str) -> str:
    if "姓名" in html and "职务" in html:
        return html
    try:
        return html.encode("cp1250", errors="strict").decode("gb18030", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return html


def fetch_online_html(page_url: str) -> str:
    response = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return response.content.decode("gb18030", errors="replace")


def parse_cards(html: str, page_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(page_rule["leader_region_selector"]):
        info = card.select_one(".qqGrade_Right_06-01b01")
        if not info:
            continue
        lines = [clean_text(line) for line in info.get_text("\n", strip=True).splitlines() if clean_text(line)]
        name = lines[1] if len(lines) >= 4 and re.sub(r"[\s：:]+", "", lines[0]) == "姓名" else ""
        duty = lines[3] if len(lines) >= 4 and re.sub(r"[\s：:]+", "", lines[2]) == "职务" else ""
        anchor = card.select_one("a[href]")
        detail_url = urljoin(page_url, str(anchor.get("href") or "").strip()) if anchor else ""
        name = re.sub(r"\s+", "", name)
        if name and duty:
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_cards；pagination=entry_plus_index_1；work_division=excluded"})
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    entry_html = normalize_entry_html(html)
    second_url = urljoin(final_url, "index_1.html")
    all_rows = parse_cards(entry_html, final_url, page_rule)
    all_rows.extend(parse_cards(fetch_online_html(second_url), second_url, page_rule))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in all_rows:
        if row["name"] in seen:
            continue
        seen.add(row["name"])
        rows.append(row)
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
