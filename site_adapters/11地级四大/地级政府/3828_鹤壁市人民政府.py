from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def normalize_url(value: str) -> str:
    """规范化网页地址，用于识别同址链接。"""
    parsed = urlsplit(str(value or "").strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从详情页左侧政府领导列表的独立姓名、职务字段提取。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".main_l .ldlist")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    entry_url = str(page_rule.get("url", "")) or source_url
    rows: list[dict[str, str]] = []
    for link in region.select("li > a[href]"):
        name_node = link.select_one(".zw1")
        duty_node = link.select_one(".zw2")
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "") if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            candidate_url = urljoin(source_url, str(link.get("href") or ""))
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": "" if normalize_url(candidate_url) == normalize_url(entry_url)
                         else candidate_url,
                         "confidence": "high", "parser": "page_inline_hebi_government_sidebar_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3828", "page_type": "详情页内领导列表", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_hebi_government_sidebar_v1", "leader_region_selector": ".main_l .ldlist",
    "name_selector": ".zw1", "duty_selector": ".zw2", "detail_link_selector": "li > a[href]",
    "locator_strategy": "custom_parse_page", "risk_flag": "", "confidence": "high",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
