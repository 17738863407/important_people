from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())

def normalize_url(value: str) -> str:
    """规范化网页地址，用于识别同址链接。"""
    parsed = urlsplit(str(value or "").strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))

def detail_url_or_blank(candidate: str, entry_url: str) -> str:
    """入口页本身不是独立人物详情页，同址时必须留空。"""
    return "" if normalize_url(candidate) == normalize_url(entry_url) else candidate

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """直接解析领导目录；兼容旧入口页动态发现目录。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy
    first = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    entry_url = str(page_rule.get("url", "")) or source
    if first.select_one(".pic-content .pic-tab"):
        soup = first
        list_final_url = source
    else:
        list_anchor = next(
            (
                anchor
                for anchor in first.select("a[href]")
                if clean_text(anchor.get_text(" ", strip=True)) == "市政府领导"
                and normalize_url(urljoin(source, str(anchor.get("href") or "")))
                != normalize_url(source)
            ),
            None,
        )
        if list_anchor is None:
            raise RuntimeError("入口页未发现可验证的市政府领导目录链接或领导卡片")
        list_url = urljoin(source, str(list_anchor.get("href") or ""))
        rendered = fetch_html_with_strategy(list_url, strategy="playwright", timeout=35)
        soup = BeautifulSoup(rendered.html, "html.parser")
        list_final_url = rendered.final_url

    rows = []
    for group in soup.select(".pic-content .pic-tab"):
        special = group.select_one(".pic-item-box-1")
        if special:
            anchors = special.select("a[href]")
            if len(anchors) >= 2:
                duty, name = clean_text(anchors[0].get_text(" ", strip=True)), clean_text(anchors[-1].get_text(" ", strip=True)).replace(" ", "")
                if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                    candidate_url = urljoin(list_final_url, str(anchors[-1].get("href") or ""))
                    rows.append({"name": name, "duty": "", "evidence": duty,
                                 "detail_url": detail_url_or_blank(candidate_url, entry_url),
                                 "confidence": "high", "parser": "page_inline_qujing_discovered_leader_list_v1"})
        title_node = group.select_one("h3.szf_h3")
        duty = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if not duty: continue
        for card in group.select(".pic-item-dl"):
            anchor = card.select_one(".pic-item-dd a[href]")
            name = clean_text(anchor.get_text(" ", strip=True) if anchor else "").replace(" ", "")
            if anchor and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                candidate_url = urljoin(list_final_url, str(anchor.get("href") or ""))
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": detail_url_or_blank(candidate_url, entry_url),
                             "confidence": "high", "parser": "page_inline_qujing_discovered_leader_list_v1"})
    return rows

PAGE_RULE = {"rule_id": "3875", "page_type": "详情页跳转领导目录", "load_mode": "Playwright渲染",
             "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_qujing_discovered_leader_list_v1", "leader_region_selector": ".pic-content",
             "name_selector": ".pic-item-dd a, .pic-item-box-1 a", "duty_selector": ".szf_h3, .pic-item-box-1 a",
             "detail_link_selector": ".pic-content a[href]", "locator_strategy": "custom_parse_page",
             "risk_flag": "主表入口为单人详情，动态发现并浏览器加载领导目录", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
