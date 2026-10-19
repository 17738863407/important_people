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
    "rule_id": "0310",
    "page_type": "多人物详情合并页",
    "structure_group": "对外友协现任领导列表转详情",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_list_online_detail_cpaffc_leader_v2",
    "leader_region_selector": "div.contentBox div.content",
    "name_selector": "a[href*='/lishihui_detail/']",
    "duty_selector": "详情页 div.detailBox > div.title",
    "detail_link_selector": "a[href*='/lishihui_detail/']",
    "risk_flag": "入口页存在误触发搜索跳转脚本，使用raw_http保留权威原始HTML",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page_with_online_detail",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_detail_duty(detail_url: str) -> str:
    """使用公共原始HTTP采集器取得详情页明确职务标题。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(detail_url, strategy="raw_http", timeout=30)
    soup = BeautifulSoup(result.html, "html.parser")
    title = soup.select_one("div.detailBox > div.title")
    return clean_text(title.get_text(" ", strip=True) if title else "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口页人物顺序抓取详情页职务标题。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    base_url = final_url or page_rule["url"]
    links = soup.select("div.contentBox div.content a[href*='/lishihui_detail/']")
    if not links:
        raise RuntimeError("未定位到对外友协现任领导详情链接")

    for link in links:
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        duty = fetch_detail_duty(detail_url)
        if not duty:
            raise RuntimeError(f"详情页未取得明确职务标题：{name}")
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_list_online_detail_cpaffc_leader_v2",
                "selector_summary": (
                    "strategy=custom_parse_page_with_online_detail；"
                    "list=div.contentBox div.content a[href*=/lishihui_detail/]；"
                    "detail_duty=div.detailBox>div.title"
                ),
            }
        )

    if not rows:
        raise RuntimeError("对外友协领导详情链未抽取到有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
