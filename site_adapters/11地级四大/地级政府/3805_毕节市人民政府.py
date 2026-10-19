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
    "rule_id": "3805", "domain": "www.bijie.gov.cn", "page_type": "政务公开首页领导列表转详情页",
    "load_mode": "静态HTML直出并逐详情请求", "fetch_mode": "online", "extract_mode": "list_to_detail",
    "collector": "raw_http", "parser": "page_inline_bijie_government_home_leaders_v2",
    "leader_region_selector": ".Part1 .aBox", "name_selector": ".ldxx a[title], .list a[title]", "duty_selector": ".Main.ldMain .part1 .profile",
    "detail_link_selector": ".ldxx a[href][title], .list a[href][title]", "content_scope": {"start_anchor": "领导之窗", "end_anchor": "机构设置", "include_selectors": [".Part1 .aBox"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "dynamic_list_links", "max_detail_links": 20},
    "risk_flag": "政务公开首页的领导之窗按页面顺序展示姓名；详情页须保留原始HTML，避免脚本跳转到无关互动页面", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ").replace("\u200b", "")).strip()


def extract_duty(detail_html: str, name: str) -> str:
    """从当前人物详情页简介中的现职句提取职务证据。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".Main.ldMain .part1")
    profile = region.select_one(".profile") if region else None
    if profile is None:
        return ""
    match = re.search(r"现任([^。]+)", clean_text(profile.get_text(" ", strip=True)))
    return clean_text(match.group(1)).rstrip("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按政务公开首页领导之窗的原始顺序抓取各人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".Part1 .aBox")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select(".ldxx a[href][title], .list a[href][title]"):
        name = re.sub(r"\s+", "", clean_text(str(link.get("title", ""))))
        href = str(link.get("href", "")).strip()
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or "/zwgk/ldzc/" not in href:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, href)
        fetched = fetch_html_with_strategy(detail_url, strategy="raw_http", force_browser=False, timeout=30)
        duty = extract_duty(fetched.html, name)
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": fetched.final_url,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "首页.Part1领导之窗链接及详情.Main.ldMain .part1 .profile现职句"})
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
