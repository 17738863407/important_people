from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3796", "domain": "www.yichang.gov.cn", "page_type": "逐人简介列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_yichang_people_congress_profiles_v1",
    "leader_region_selector": ".ldjstxt87", "name_selector": "h1 a[href]", "duty_selector": "p",
    "detail_link_selector": "h1 a[href]", "content_scope": {"start_anchor": "人大领导", "end_anchor": "", "include_selectors": [".ldjstxt87"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "职务嵌在每个人物简介的现任句中，需逐卡片限定", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ").replace("\u200b", "")).strip()


def page_key(value: str) -> tuple[str, str, str]:
    """生成忽略协议、片段和末尾斜杠的页面键，用于识别入口页同址链接。"""
    parts = urlsplit(clean_text(value))
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        host = f"{host}:{port}"
    path = (parts.path or "/").rstrip("/") or "/"
    return host, path, parts.query


def resolve_detail_url(href: str, base_url: str, source_url: str) -> str:
    """仅保留可验证的独立HTTP详情页，入口同址或脚本伪链接均留空。"""
    raw_href = clean_text(href)
    if not raw_href or raw_href.lower().startswith(("#", "javascript:", "mailto:")):
        return ""
    detail_url = urljoin(base_url or source_url, raw_href)
    if urlsplit(detail_url).scheme.lower() not in {"http", "https"}:
        return ""
    detail_key = page_key(detail_url)
    source_keys = {page_key(url) for url in (base_url, source_url) if clean_text(url)}
    return "" if detail_key in source_keys else detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", ""))
    base_url = final_url or source_url
    rows: list[dict[str, str]] = []
    for card in soup.select(".ldjstxt87"):
        link = card.select_one("h1 a[href]")
        if not link:
            continue
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        profile = next((clean_text(node.get_text(" ", strip=True)) for node in card.select("p") if "现任" in node.get_text()), "")
        match = re.search(r"现任([^。]+)", profile)
        duty = clean_text(match.group(1)).rstrip("；;，,。") if match else ""
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            detail_url = resolve_detail_url(str(link.get("href", "")), base_url, source_url)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
