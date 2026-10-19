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
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def iter_leader_links(html: str, base_url: str) -> list[str]:
    """按页面顺序提取领导之窗中的独立详情页链接。"""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/zwfw/jcxxgk/ldzc/"]'):
        name = clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not re.search(r"/ldzc/\d{6}/t\d+_\d+\.html", href):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen:
            continue
        seen.add(detail_url)
        urls.append(detail_url)
    return urls


def extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """从详情页人物表格提取姓名与担任职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    table = soup.select_one("table")
    text = clean_text(table.get_text(" ", strip=True) if table else "")
    name_match = re.search(r"姓\s*名[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,8})", text)
    duty_match = re.search(
        r"担任职务[:：]\s*(?P<duty>.*?)(?:\s+性\s*别[:：]|\s+民\s*族[:：]|\s+出生日期[:：]|$)",
        text,
    )
    name = clean_text(name_match.group("name")) if name_match else ""
    duty = clean_text(duty_match.group("duty")) if duty_match else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口DOM顺序在线请求详情并提取人物表格强字段。"""
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    for source_order, detail_url in enumerate(iter_leader_links(html, final_url), start=1):
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = extract_detail_fields(response.text)
        if not name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "page_inline_guizhou_ggzy_detail_table_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0708",
    "page_type": "人物表格页",
    "structure_group": "贵州公共资源领导列表转详情表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_ggzy_detail_table_v2",
    "leader_region_selector": ".ldzc_right",
    "name_selector": "详情页table姓名字段",
    "duty_selector": "详情页table担任职务字段",
    "detail_link_selector": 'a[href*="/zwfw/jcxxgk/ldzc/"]',
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "详情页同时含分工文本，证据边界必须限制在人物信息表格",
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
