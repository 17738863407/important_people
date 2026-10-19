from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3225",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_emergency_jpage_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌JPage数据",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_lanzhou_emergency_jpage_detail_current_sentence_v1",
    "leader_region_selector": "div[id='83912'] script[type='text/xml'] record",
    "name_selector": "record CDATA a[title]",
    "duty_selector": "人物详情页#zoom完整现任句",
    "detail_link_selector": "record CDATA a[href]",
    "detail_strategy": {"required": True, "mode": "dynamic_list_to_detail", "detail_link_selector": "record CDATA a[href]", "detail_content_selector": "#zoom", "max_detail_links": 15},
    "risk_flag": "historical_script_hardcoded_people_and_page_only_has_hidden_visitcount_iframe",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_datastore_selector": "div[id='83912'] script[type='text/xml']", "detail_content_selector": "#zoom"},
        "api": {"enabled": False, "reason": "当前原始HTTP页面内嵌8个领导JPage record，各详情#zoom含完整现任句"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def extract_current_sentence(detail_html: str, expected_name: str) -> str:
    """校验详情姓名并提取同一人物正文的完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return ""
    text = normalize_space(container.get_text(" ", strip=True))
    if expected_name not in re.sub(r"\s+", "", text):
        return ""
    match = re.search(r"现任[^。]{2,200}。", text)
    return normalize_space(match.group(0)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按JPage record顺序动态读取姓名链接和详情现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="83912")
    datastore = container.find("script", attrs={"type": "text/xml"}) if container else None
    if datastore is None or not datastore.string:
        return []
    records = BeautifulSoup(str(datastore.string), "html.parser").find_all("record")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        fragment = BeautifulSoup(str(record.string or ""), "html.parser")
        link = fragment.find("a", href=True)
        if link is None:
            continue
        name = re.sub(r"\s+", "", normalize_space(str(link.get("title", "")) or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            evidence = extract_current_sentence(response.text, name)
        except requests.RequestException:
            continue
        if not evidence:
            continue
        seen.add(name)
        duty = evidence.removeprefix("现任").rstrip("。").strip()
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "原始HTTP JPage record顺序与动态姓名链接；详情#zoom校验姓名后提取完整现任句"})
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
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
