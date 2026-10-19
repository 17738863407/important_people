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
    "rule_id": "0079",
    "domain": "amr.gd.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "guangdong_market_supervision_leader_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guangdong_market_supervision_leader_detail_v1",
    "leader_region_selector": "ul.news_list2 > li",
    "name_selector": "h3 a[href]",
    "detail_link_selector": "h3 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_content_selector": ".article_con",
        "duty_start": "姓名：",
        "duty_end": "工作分工：",
    },
    "risk_flag": "列表仅含姓名和日期；职务位于详情页姓名冒号后的首行，须在工作分工前截断",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def extract_duty(detail_html: str, name: str, selector: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(selector)
    if region is None:
        return ""
    for node in region.select("p"):
        text = clean_text(node.get_text(" ", strip=True))
        match = re.fullmatch(rf"{re.escape(name)}[：:]\s*(.+)", text)
        if match is not None:
            return match.group(1).strip()
    return ""


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表顺序在线取得详情页明确职务首行。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    detail_selector = str(page_rule["detail_strategy"]["detail_content_selector"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        link = item.select_one(str(page_rule["detail_link_selector"]))
        name = clean_text(link.get_text(" ", strip=True) if link else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen or link is None:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            detail_html = fetch_detail_html(session, detail_url)
        except requests.RequestException:
            continue
        evidence = extract_duty(detail_html, name, detail_selector)
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )
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
