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
    """压缩详情简介中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """去除姓名内部排版空白。"""
    return clean_text(value).replace(" ", "")


def extract_detail(detail_html: str, listed_name: str) -> str:
    """从人物简介首句提取姓名后的完整现任职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(".ldxl-x2 .TRS_UEDITOR") or soup.select_one(".ldxl-x2")
    text = clean_text(node.get_text(" ", strip=True) if node else "")
    match = re.match(rf"{re.escape(listed_name)}[，,]\s*(?P<duty>.+?)[。]\s*(?:男|女)[，,]", text)
    return clean_text(match.group("duty")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按省局领导卡片顺序在线请求详情并提取完整职务。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = ".gkpd-ld a[href], .gkpd-ldd a[href]"

    for source_order, link in enumerate(soup.select(selector), start=1):
        name_node = link.select_one("em")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        duty = extract_detail(response.text, name)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_hainan_amr_online_details_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0083",
    "page_type": "人物列表完整页",
    "structure_group": "海南市场监管局领导卡片转详情简介",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hainan_amr_online_details_v2",
    "leader_region_selector": ".gkpd-ld, .gkpd-ldd",
    "name_selector": ".gkpd-ld a em, .gkpd-ldd a em",
    "duty_selector": "详情.ldxl-x2人物简介首句姓名后职务",
    "detail_link_selector": ".gkpd-ld a[href], .gkpd-ldd a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "入口部分长职务被省略号截断，必须逐详情读取人物简介首句完整职务；分工另有明确边界",
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
