from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3904",
    "page_type": "错误入口导航至政府领导页",
    "structure_group": "yichang_cross_tab_government_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "navigation_to_scoped_cards",
    "collector": "requests",
    "parser": "page_inline_yichang_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ldzc-list1",
    "name_selector": ".ldjstxt87 h1 a",
    "duty_selector": ".ldjstxt87 p内完整现任句",
    "detail_link_selector": ".ldjstxt87 h1 a[href]",
    "target_timeout_seconds": 35,
    "risk_flag": "依据入口实际为市委领导页；须通过页内领导之窗导航动态进入市政府领导页后解析，禁止从市委页筛人",
    "confidence": "high",
    "filter_policy": "verified_current_sentence",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_current_sentence(value: str) -> str:
    """删除已定位现任句的句首固定标签和纯句末句号。"""
    return re.sub(r"^现任\s*", "", clean_text(value), count=1).removesuffix("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """由领导之窗导航进入政府页，再按人物卡片原始顺序提取。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = final_url or page_rule["url"]
    entry_soup = BeautifulSoup(html, "lxml")
    target_link = next(
        (
            link
            for link in entry_soup.select("a[href]")
            if clean_text(link.get_text(" ", strip=True)) == "市政府领导"
        ),
        None,
    )
    if target_link is None:
        raise RuntimeError("市委入口页未找到市政府领导导航链接")
    target_url = urljoin(entry_url, clean_text(target_link.get("href")))
    target_result = fetch_html_with_strategy(
        target_url,
        strategy="requests",
        timeout=int(page_rule["target_timeout_seconds"]),
    )
    target_soup = BeautifulSoup(target_result.html, "lxml")
    region = target_soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("市政府领导页未找到人物卡片列表")

    base_url = target_result.final_url or target_url
    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select("li"):
        name_link = card.select_one(".ldjstxt87 h1 a")
        name = clean_name(name_link.get_text(" ", strip=True) if name_link else "")
        current_match = None
        for paragraph in card.select(".ldjstxt87 p"):
            current_match = re.search(r"现任[^。]*。", clean_text(paragraph.get_text(" ", strip=True)))
            if current_match:
                break
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or current_match is None:
            continue
        if name in seen_names:
            continue
        href = clean_text(name_link.get("href")) if name_link else ""
        detail_url = urljoin(base_url, href) if href else ""
        if urlparse(detail_url).scheme not in {"http", "https"}:
            detail_url = ""
        evidence = clean_current_sentence(current_match.group(0))
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "领导之窗市政府导航；.ldzc-list1卡片内姓名与完整现任句",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导人物卡片未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
