from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3604", "domain": "www.ruc.edu.cn", "page_type": "学校领导多栏目名单",
    "structure_group": "ruc_current_leader_sections_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "leader_cards_and_heading_lists",
    "collector": "static_http", "parser": "page_ruc_current_leaders_v1", "leader_region_selector": ".xrld-page1",
    "name_selector": ".xrld-item p a, p.pl30 a", "duty_selector": ".xrld-item h5, h4.xrld-title",
    "detail_link_selector": ".xrld-item p a[href]", "detail_strategy": {"required": False, "mode": "validated_person_link", "candidate_links": []},
    "risk_flag": "exclude_visibility_hidden_and_merge_multi_duties", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """清理纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def add_person(store: dict[str, dict[str, object]], name: str, duties: list[str], detail_url: str) -> None:
    """按首次出现顺序保存人物，并合并网页明示的不同职务。"""
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name): return
    row = store.setdefault(name, {"duties": [], "detail_url": detail_url})
    for duty in duties:
        if duty and duty not in row["duties"]: row["duties"].append(duty)
    if not row["detail_url"] and detail_url: row["detail_url"] = detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导班子、党委常委、校长助理栏目顺序抽取并合并同人职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xrld-page1")
    if region is None:
        response = requests.get(str(page_rule.get("url", "")), timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        final_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")
        region = soup.select_one(".xrld-page1")
    if region is None: return []
    store: dict[str, dict[str, object]] = {}
    for item in region.select(".xrld-item"):
        heading = item.select_one("h5")
        if heading is None: continue
        duties = [clean(" ".join(str(x) for x in heading.find_all(string=True, recursive=False)))]
        duties.extend(clean(span.get_text(" ", strip=True)) for span in heading.select(":scope > span"))
        for link in item.select("p a[href]"):
            if "visibility:hidden" in str(link.get("style", "")).replace(" ", "").lower(): continue
            name = clean(link.get_text(" ", strip=True))
            href = str(link.get("href", ""))
            detail = urljoin(final_url, href) if href and not href.lower().startswith("javascript:") else ""
            add_person(store, name, duties, detail)
    for heading in region.select("h4.xrld-title"):
        duty = clean(" ".join(str(node) for node in heading.find_all(string=True, recursive=False)))
        if duty == "学校领导班子成员": continue
        listing = heading.find_next_sibling("p")
        if not isinstance(listing, Tag) or "pl30" not in listing.get("class", []): continue
        for link in listing.select("a"):
            add_person(store, clean(link.get_text(" ", strip=True)), [duty], "")
    return [{"name": name, "duty": "；".join(data["duties"]), "evidence": "；".join(data["duties"]),
             "detail_url": str(data["detail_url"]), "parser": str(page_rule.get("parser", "")),
             "selector_summary": "strategy=custom_parse_page；region=.xrld-page1；sections=.xrld-item+h4.xrld-title+p.pl30；hidden=excluded；duties=merged"}
            for name, data in store.items() if data["duties"]]


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
