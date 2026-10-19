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


def extract_duty(detail_html: str) -> str:
    """从详情人物区提取担任职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    box = soup.select_one(".ldzc")
    text = clean_text(box.get_text(" ", strip=True) if box else "")
    match = re.search(r"担任职务：\s*(?P<duty>.+?)\s*领导分工：", text)
    return clean_text(match.group("duty")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗目录顺序在线请求详情并提取担任职务。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".ldzc")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate((box or soup).select("a[href]"), start=1):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        if not re.search(r"/ldzc/\d{6}/t\d+_\d+\.html", detail_url):
            continue
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        duty = extract_duty(response.text)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "custom_guizhou_stats_online_details_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2586",
    "page_type": "人物列表完整页",
    "structure_group": "贵州统计局领导目录转详情字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_guizhou_stats_online_details_v2",
    "leader_region_selector": ".ldzc",
    "name_selector": ".ldzc人物详情链接文本",
    "duty_selector": "详情.ldzc担任职务字段",
    "detail_link_selector": ".ldzc a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "人物区含javascript标签链接，详情候选必须同时满足人物姓名和领导详情文件路径",
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
