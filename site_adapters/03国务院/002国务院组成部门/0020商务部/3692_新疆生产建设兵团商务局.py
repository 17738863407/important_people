from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3692", "page_type": "首页领导列表转人物详情页",
    "structure_group": "xjbt_swj_home_leader_details_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出并逐详情请求", "fetch_mode": "online", "extract_mode": "list_to_detail",
    "collector": "static_http", "parser": "xjbt_swj_home_leader_details_v1",
    "leader_region_selector": ".p-md.leader .swiper-leader",
    "name_selector": ".p-md.leader .swiper-leader .leader-item .leadTit a[href]",
    "duty_selector": "#detail-con .content p",
    "detail_link_selector": ".p-md.leader .swiper-leader .leader-item .leadTit a[href]",
    "content_scope": {
        "include_selectors": [".p-md.leader .swiper-leader .leader-item"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "dynamic_home_cards", "max_detail_links": 20},
    "risk_flag": "首页领导卡片DOM顺序为权威人物顺序；职务取对应详情正文首个姓名职务段，后续为简历和分工",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value).strip()


def _extract_duty(detail_html: str, name: str) -> str:
    """从详情正文第一个“姓名+职务”段取得职务，排除随后简历及分工。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select("#detail-con .content p"):
        text = _compact(paragraph.get_text(" ", strip=True))
        if not text.startswith(name):
            continue
        remainder = text[len(name):].strip("：:")
        if remainder and not remainder.startswith(("，", ",")):
            return "；".join(part for part in re.split(r"[、，,；;]", remainder) if part)
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按首页领导卡片的展示顺序取得详情链接，再逐页提取首个职务段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".p-md.leader .swiper-leader")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in region.select(".leader-item"):
        anchor = card.select_one(".leadTit a[href]")
        if anchor is None:
            continue
        name = _compact(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href", "")).strip()
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or "/c/" not in href:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, href)
        fetched = fetch_html_with_strategy(detail_url, strategy="requests", force_browser=False, timeout=30)
        duty = _extract_duty(fetched.html, name)
        if not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": fetched.final_url,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "首页领导卡片DOM顺序、.leadTit链接及详情#detail-con首个姓名职务段",
        })
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
