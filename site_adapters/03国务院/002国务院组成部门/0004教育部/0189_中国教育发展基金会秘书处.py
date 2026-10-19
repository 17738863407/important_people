from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "0189",
    "page_type": "人物列表完整页",
    "structure_group": "cedf_secretariat_iframe_text",
    "load_mode": "iframe嵌入",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_cedf_secretariat_iframe_v1",
    "leader_region_selector": 'iframe[src*="/gywm/zuzhijigou/mishuchu/index.html"]',
    "name_selector": ".textConten p",
    "duty_selector": ".textConten p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "仅解析官方CMS iframe正文中秘书长和副秘书长两行，排除部门及联系电话",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线读取官方CMS iframe，只解析秘书长与副秘书长原文行。"""
    import re
    from urllib.parse import urlsplit

    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_by_chrome_debug_subprocess

    outer_soup = BeautifulSoup(html, "html.parser")
    iframe = outer_soup.select_one('iframe[src*="/gywm/zuzhijigou/mishuchu/index.html"]')
    if iframe is None:
        return []
    iframe_url = str(iframe.get("src") or "").strip()
    parts = urlsplit(iframe_url)
    if parts.scheme != "https" or parts.hostname != "cms.cedf.org.cn":
        return []

    iframe_result = fetch_by_chrome_debug_subprocess(
        iframe_url,
        timeout=30,
    )
    iframe_soup = BeautifulSoup(iframe_result.html, "html.parser")

    rows: list[dict[str, str]] = []
    for node in iframe_soup.select(".textConten p"):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        match = re.fullmatch(
            r"(?P<duty>秘\s*书\s*长|副秘书长)\s*[：:]\s*(?P<names>[\u4e00-\u9fff·\s]+)",
            text,
        )
        if match is None:
            continue
        duty = re.sub(r"\s+", "", match.group("duty"))
        names_text = re.sub(r"\s+", " ", match.group("names")).strip()
        for name in re.findall(r"[\u4e00-\u9fff·]{2,8}", names_text):
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")),
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_cedf_secretariat_iframe_v1",
                    "detail_url": "",
                }
            )
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
