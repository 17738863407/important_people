from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2350",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_agency_affairs_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_agency_affairs_directory_details_v1",
    "leader_region_selector": "#xxgkzd_list li",
    "name_selector": "#xxgkzd_list li a[href]",
    "duty_selector": ".gknbxq_detail p",
    "detail_link_selector": "#xxgkzd_list li a[href]",
    "content_scope": {
        "start_anchor": "领导班子目录首项",
        "end_anchor": "领导班子目录末项",
        "include_selectors": ["#xxgkzd_list li a[href]"],
        "exclude_selectors": ["左侧公开栏目", "分工段", "导航与页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "#xxgkzd_list li a[href]",
        "detail_name_selector": ".gknbxq_detail p中的姓名标题或本人简介",
        "detail_duty_selector": ".gknbxq_detail p中的姓名：职务或现任句",
        "detail_content_selector": ".gknbxq_detail",
        "max_detail_links": 50,
    },
    "risk_flag": "部分详情页没有姓名：职务标题；仅在当前人物.gknbxq_detail段落内回退提取完整现任句，禁止扫描全页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#xxgkzd_list li",
            "name_selector": "a[href]",
            "duty_selector": ".gknbxq_detail p",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "领导班子目录首项",
                "end_anchor": "领导班子目录末项",
                "include_selectors": ["#xxgkzd_list li a[href]", ".gknbxq_detail p"],
                "exclude_selectors": ["左侧公开栏目", "分工段", "导航与页脚"],
            },
        },
        "api": {"enabled": False, "reason": "目录及人物详情均由静态HTML直接提供，未发现必要接口"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if str(current.get("id", "")) == "xxgkzd_list":
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if "/sgj/ldbz/20" not in parsed.path or not parsed.path.endswith(".shtml"):
        return ""
    return resolved


def _extract_detail(name: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".gknbxq_detail")
    if scope is None:
        return "", ""
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in scope.select("p")]
    paragraphs = [text for text in paragraphs if text and not text.startswith("分工：")]
    spaced_name = r"\s*".join(re.escape(char) for char in name)
    for text in paragraphs:
        match = re.fullmatch(spaced_name + r"\s*[：:]\s*(.+)", text)
        if match is not None:
            duty = _clean_text(match.group(1)).strip("。；;")
            if duty:
                return duty, duty
    for text in paragraphs:
        if name not in re.sub(r"\s+", "", text):
            continue
        match = re.search(r"现任[^。]*。", text)
        if match is not None:
            evidence = _clean_text(match.group(0))
            duty = evidence.removeprefix("现任").rstrip("。")
            if duty:
                return duty, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#xxgkzd_list li a[href]"):
        if _is_hidden(link):
            continue
        name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        detail_url = _detail_url(base_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not detail_url or name in seen:
            continue
        seen.add(name)
        duty = ""
        evidence = ""
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            duty, evidence = _extract_detail(name, response.text)
        except requests.RequestException:
            pass
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_xinjiang_agency_affairs_directory_details_v1",
                "selector_summary": "#xxgkzd_list目录；详情.gknbxq_detail姓名标题或本人现任句",
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
