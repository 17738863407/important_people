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


def clean_text(value: str) -> str:
    """压缩网页字段的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """去除姓名内部的排版空白。"""
    return clean_text(value).replace(" ", "")


def extract_detail(detail_html: str) -> tuple[str, str]:
    """从详情首个信息表格提取姓名与职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    table = soup.select_one(".Article_zw table") or soup.select_one("table")
    text = clean_text(table.get_text(" ", strip=True) if table else "")
    match = re.search(r"姓\s*名：\s*(?P<name>.+?)\s*职\s*务：\s*(?P<duty>.+?)\s*领导职责：", text)
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导介绍卡片顺序在线请求详情并提取个人强字段。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select('a[href*="ldjs_5982321"]'), start=1):
        listed_name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", listed_name) or listed_name in seen:
            continue
        if not re.search(r"/ldjs_5982321/\d{6}/t\d+_\d+\.html", detail_url):
            continue
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = extract_detail(response.text)
        if name != listed_name:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_wsg_online_details_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2978",
    "page_type": "人物列表完整页",
    "structure_group": "贵州文史馆领导卡片转详情表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_wsg_online_details_v2",
    "leader_region_selector": ".ConBox .PicList",
    "name_selector": 'a[href*="ldjs_5982321"]人物链接文本',
    "duty_selector": "详情.Article_zw首个table职务字段",
    "detail_link_selector": 'a[href*="ldjs_5982321"]',
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "卡片图片和姓名形成重复链接，按非空姓名及详情文件路径去重；职务以详情表格为准",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
