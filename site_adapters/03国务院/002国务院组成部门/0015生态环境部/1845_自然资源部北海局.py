from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "1845",
    "page_type": "人物列表完整页",
    "structure_group": "mnr_north_sea_leaders_iframe",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_mnr_north_sea_leaders_iframe_v1",
    "leader_region_selector": "iframe[src*='/n1/n292/n293/']",
    "name_selector": "td[style*='line-height'] > p",
    "duty_selector": "td[style*='line-height'] > p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物信息在唯一iframe中；最后一人现任句跨段排版，须在单人物块内连续拼接",
    "confidence": "high",
}


def _compact_text(text: str) -> str:
    """仅清理HTML排版空白，不改变原文语义。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """读取唯一领导iframe，并按人物基本信息段划分现任职务块。"""
    import requests
    from bs4 import BeautifulSoup

    outer_soup = BeautifulSoup(html, "html.parser")
    iframe = outer_soup.select_one("iframe[src*='/n1/n292/n293/']")
    if iframe is None:
        return []
    iframe_url = urljoin(final_url, str(iframe.get("src") or ""))
    response = requests.get(
        iframe_url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    iframe_soup = BeautifulSoup(response.text, "html.parser")

    rows: list[dict[str, str]] = []
    current_name = ""
    current_lines: list[str] = []

    def append_current() -> None:
        if not current_name:
            return
        block_text = "".join(current_lines)
        match = re.search(r"现任[^。]*。", block_text)
        if match is None:
            return
        evidence = match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": current_name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_mnr_north_sea_leaders_iframe_v1",
            }
        )

    for paragraph in iframe_soup.select("td[style*='line-height'] > p"):
        text = _compact_text(paragraph.get_text("", strip=True))
        if not text:
            continue
        person_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,5})，[男女]，", text)
        if person_match:
            append_current()
            current_name = person_match.group("name")
            current_lines = [text]
        elif current_name:
            current_lines.append(text)
    append_current()
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
