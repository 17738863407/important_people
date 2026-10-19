from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": "0541", "page_type": "列表转人物详情页", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "页面内置parse_page", "leader_region_selector": ".leader_xx, .leader_xm", "risk_note": "主页领导与其他领导链接结构不同；详情.leader_content h3按“职务 姓名”展示。", "confidence": "high"}

def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()

def compact(value: str) -> str:
    """移除排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))

def leader_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    """按页面顺序合并主要领导和其他领导链接。"""
    pairs: list[tuple[str, str]] = []
    main_link = soup.select_one(".leader_xx a[href]")
    main_name = soup.select_one(".leader_xx h6 b")
    if main_link and main_name:
        pairs.append((compact(main_name.get_text(" ", strip=True)), urljoin(base_url, (main_link.get("href") or "").strip())))
    for link in soup.select(".leader_xm a[href]"):
        name = compact(link.get_text(" ", strip=True) or link.get("title", ""))
        detail_url = urljoin(base_url, (link.get("href") or "").strip())
        if name and detail_url not in {item[1] for item in pairs}:
            pairs.append((name, detail_url))
    return pairs

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """读取详情标题中姓名前的原始职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for name, detail_url in leader_links(soup, final_url):
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        heading = clean_text(detail_soup.select_one(".leader_content h3").get_text(" ", strip=True)) if detail_soup.select_one(".leader_content h3") else ""
        match = re.match(rf"(?P<duty>.+?)\s+{''.join(re.escape(char) + r'\s*' for char in name)}$", heading)
        if match:
            rows.append({"name": name, "duty": "", "evidence": clean_text(match.group("duty")), "detail_url": result.final_url})
    return rows

def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
