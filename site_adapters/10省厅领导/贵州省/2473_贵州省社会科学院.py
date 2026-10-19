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


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按组织机构页领导之窗链接顺序在线请求详情并提取职务。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select('a[href*="/ldzc_4511431/"]'), start=1):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        if not re.search(r"/ldzc_4511431/\d{6}/t\d+_\d+\.html", detail_url):
            continue
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        duty_node = detail_soup.select_one(".drzz")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "custom_guizhou_academy_leader_details_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2473",
    "page_type": "人物列表完整页",
    "structure_group": "贵州社科院组织机构领导目录转详情",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_guizhou_academy_leader_details_v2",
    "leader_region_selector": 'a[href*="/ldzc_4511431/"]',
    "name_selector": 'a[href*="/ldzc_4511431/"]人物链接文本',
    "duty_selector": "详情页.drzz",
    "detail_link_selector": 'a[href*="/ldzc_4511431/"]',
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "组织机构页还含机构设置与科研团队链接，人物链接须同时满足领导栏目路径和详情文件格式",
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
