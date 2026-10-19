from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0609", "page_type": "人物目录详情页", "structure_group": "guiyang_police_leader_list_bio_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc", "name_selector": "a[href*='/jgld01/'][href$='.html']", "duty_selector": "detail table 简历字段中的现任或政治面貌后现职片段",
    "detail_link_selector": ".zfxxgk_zdgkc a[href*='/jgld01/'][href$='.html']",
    "content_scope": {"start_anchor": "机构领导", "end_anchor": "版权信息", "include_selectors": [".zfxxgk_zdgkc"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "详情表格简历与分工分列；现职或由现任标记，或位于中共党员字段之后", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def read_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        label = compact_text(cells[0].get_text(" ", strip=True))
        if label in {"姓名", "简历"}:
            fields[label] = compact_text(cells[1].get_text(" ", strip=True))
    name = fields.get("姓名", "")
    biography = fields.get("简历", "")
    current_match = re.search(r"现任(?P<duty>[^。]+)", biography)
    if current_match is not None:
        return name, current_match.group("duty")
    party_match = re.search(r"中共党员[，,](?P<duty>[^。]+)$", biography)
    return name, party_match.group("duty") if party_match is not None else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取详情，并从简介单元格提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".zfxxgk_zdgkc a[href*='/jgld01/'][href$='.html']"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, "requests")
        name, evidence = read_detail(detail.html)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or not evidence or name in seen:
            continue
        duty = evidence.removesuffix("。")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url, "selector_summary": "人物目录链接；详情表格姓名字段及简历单元格完整现任句"})
        seen.add(name)
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
