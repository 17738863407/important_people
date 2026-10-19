from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3919",
    "page_type": "市政府领导名录与个人简介页",
    "structure_group": "zhoukou_government_leader_roster_profile_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "list_with_detail",
    "collector": "raw_http",
    "parser": "page_inline_zhoukou_government_leader_roster_profile_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".index-ldzc-szfld",
    "name_selector": "table a[href] > p",
    "duty_selector": "个人简介页现任句",
    "detail_link_selector": "table a[href]",
    "risk_flag": "仅从“市政府领导”名录获得姓名和个人页，再从同一人物简介页提取完整现任句；不使用新闻出席名单",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名内的排版空白并限制为中文姓名。"""
    normalized = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()
    return normalized if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", normalized) else ""


def extract_current_duty(detail_html: str, name: str) -> str:
    """从当前人物简介块内提取可验证的完整现任句。"""
    detail_soup = BeautifulSoup(detail_html, "lxml")
    for paragraph in detail_soup.select(".index-ldzcitem-text p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.search(r"现任[^。]*。", text)
        if match and name in text:
            return re.sub(r"^现任\s*", "", match.group(0)).removesuffix("。").strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """先解析市政府领导名录，再逐人核验个人简介页中的现任职务。"""
    soup = BeautifulSoup(html, "lxml")
    roster_region = soup.select_one(page_rule["leader_region_selector"])
    if roster_region is None:
        raise RuntimeError("未定位到市政府领导名录")

    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict] = []
    base_url = final_url or page_rule["url"]
    for link in roster_region.select("table a[href]"):
        name_node = link.find("p")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not name or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        evidence = extract_current_duty(detail_result.html, name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": "high" if evidence else "medium",
                "parser": page_rule["parser"],
                "selector_summary": "市政府领导名录人物链接与个人简介块现任句",
            }
        )
    if not rows:
        raise RuntimeError("市政府领导名录未解析出有效人物")
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
