from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0474",
    "page_type": "人物列表完整页",
    "structure_group": "gd_drc_left_nav_detail_h3_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "online_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".cont-left-xl",
    "name_selector": ".cont-left-xl li a[title][href]",
    "duty_selector": ".ldxqy h3",
    "detail_link_selector": ".cont-left-xl li a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_content_selector": ".ldxqy",
        "max_detail_links": 50,
    },
    "risk_flag": "首位人物链接等于机构入口页，输出详情页时必须置空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_title(target: str) -> str:
    response = requests.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    node = soup.select_one(".ldxqy h3")
    return _clean_text(node.get_text(" ", strip=True)) if node else ""


def _split_title(title: str, default_name: str) -> tuple[str, str]:
    match = re.fullmatch(r"([^：:]+)[：:](.+)", title)
    if match is None:
        return default_name, ""
    name = _clean_name(match.group(1)) or default_name
    duty = _clean_text(match.group(2)).strip("。")
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧人物列表顺序抓取详情页h3中的姓名和原始职务。"""
    del page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".cont-left-xl li a[title][href]"):
        list_name = _clean_name(link.get("title") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name):
            continue
        target = urljoin(final_url, link.get("href", ""))
        try:
            title = _fetch_title(target)
        except requests.RequestException:
            continue
        name, duty = _split_title(title, list_name)
        if not duty or name in seen:
            continue
        seen.add(name)
        independent_detail = "" if urldefrag(target)[0] == urldefrag(final_url)[0] else target
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": independent_detail,
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
