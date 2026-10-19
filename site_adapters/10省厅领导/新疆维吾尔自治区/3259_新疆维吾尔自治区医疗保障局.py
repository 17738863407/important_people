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
    "rule_id": "3259",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_medical_security_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_medical_security_directory_details_v1",
    "leader_region_selector": ".newslist.ny li",
    "name_selector": ".newslist.ny li a[title][href]",
    "duty_selector": "详情页中领导简介标题后的首个非空p",
    "detail_link_selector": ".newslist.ny li a[title][href]",
    "content_scope": {
        "start_anchor": "领导目录首项",
        "end_anchor": "领导目录末项",
        "include_selectors": [".newslist.ny li a[title][href]", "领导简介相邻职务段"],
        "exclude_selectors": ["领导履历", "主办承办", "导航与页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".newslist.ny li a[title][href]",
        "detail_name_selector": "目录姓名与详情正文对账",
        "detail_duty_selector": "领导简介标题后的首个非空p",
        "detail_content_selector": "详情正文p序列",
        "max_detail_links": 50,
    },
    "risk_flag": "详情HTML排版不统一且可能存在中文间布局空格；只在精确领导简介标题后取下一职务段并做确定性空白清理",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".newslist.ny li",
            "name_selector": "a[title][href]",
            "duty_selector": "精确领导简介p后的下一p",
            "detail_link_selector": "a[title][href]",
            "content_scope": {
                "start_anchor": "领导目录首项",
                "end_anchor": "领导目录末项",
                "include_selectors": [".newslist.ny li a[title][href]", "领导简介相邻职务段"],
                "exclude_selectors": ["领导履历", "主办承办", "导航与页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML目录和详情正文直接提供姓名、职务字段"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "newslist" in classes and "ny" in classes:
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
    if "/ylbzj/ldjs/20" not in parsed.path or not parsed.path.endswith(".shtml"):
        return ""
    return resolved


def _extract_detail(name: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    if name not in _compact_text(soup.get_text(" ", strip=True)):
        return "", ""
    for paragraph in soup.select("p"):
        if _compact_text(paragraph.get_text(" ", strip=True)) != "领导简介":
            continue
        duty_node = paragraph.find_next("p")
        while duty_node is not None and not _compact_text(duty_node.get_text(" ", strip=True)):
            duty_node = duty_node.find_next("p")
        if duty_node is None:
            return "", ""
        duty = _compact_text(duty_node.get_text(" ", strip=True))
        if "新疆维吾尔自治区医疗保障局" in duty and len(duty) < 100:
            return duty, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".newslist.ny li a[title][href]"):
        if _is_hidden(link):
            continue
        name = _compact_text(str(link.get("title", "")) or link.get_text(" ", strip=True))
        detail_url = _detail_url(base_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,30}", name) or not detail_url or name in seen:
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
                "parser": "custom_xinjiang_medical_security_directory_details_v1",
                "selector_summary": ".newslist.ny目录；详情精确领导简介标题后的职务p",
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
