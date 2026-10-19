from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按机关简介页人物顺序读取各详情页的姓名和原始职务。"""
    import re
    import requests

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".oflow-hd dl"):
        name_link = card.select_one("dd.ldname a[title]")
        if name_link is None:
            continue
        name = clean_text(name_link.get("title") or name_link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        href = str(name_link.get("href") or "")
        if not href:
            image_link = card.select_one("dt a[href]")
            href = str(image_link.get("href") or "") if image_link else ""
        if not href:
            continue
        detail_url = urljoin(final_url, href)
        response = requests.get(
            detail_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        detail_name_node = detail_soup.select_one(".TRS_Editor p.name a[title]")
        duty_node = detail_soup.select_one(".TRS_Editor p.zw a[title]")
        detail_name = clean_text(
            detail_name_node.get("title") or detail_name_node.get_text(" ", strip=True)
            if detail_name_node
            else ""
        ).replace(" ", "")
        duty = clean_text(duty_node.get("title") or duty_node.get_text(" ", strip=True) if duty_node else "")
        if detail_name != name or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "" if detail_url == str(page_rule.get("url") or "").strip() else detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_liaoning_fgw_leader_details_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0551",
    "page_type": "人物目录详情页",
    "structure_group": "liaoning_fgw_leader_details",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_liaoning_fgw_leader_details_v1",
    "leader_region_selector": ".oflow-hd",
    "name_selector": ".oflow-hd dd.ldname a[title]",
    "duty_selector": ".TRS_Editor p.zw a[title]",
    "detail_link_selector": ".oflow-hd dl dd.ldname a[href], .oflow-hd dl dt a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "首人姓名链接无href，需在同一人物卡片内读取头像详情链接",
    "confidence": "high",
}


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
