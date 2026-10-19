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
    "rule_id": "2908",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_health_portrait_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_health_portrait_directory_details_v1",
    "leader_region_selector": ".ld_list li",
    "name_selector": ".ld_list li a[href] p",
    "duty_selector": ".d_m_centre p",
    "detail_link_selector": ".ld_list li a[href]",
    "content_scope": {
        "start_anchor": "首个人物照片卡",
        "end_anchor": "末个人物照片卡",
        "include_selectors": [".ld_list li a[href]", ".d_m_centre"],
        "exclude_selectors": ["装饰图片", "我的分工", "我的简历", "导航与页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".ld_list li a[href]",
        "detail_name_selector": ".d_m_centre h2",
        "detail_duty_selector": ".d_m_centre p",
        "detail_content_selector": ".d_m_centre",
        "max_detail_links": 50,
    },
    "risk_flag": "页面含人物照片但姓名和职务已有可验证HTML文本；按规则优先HTML，不进入OCR通道",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ld_list li",
            "name_selector": "a[href] p",
            "duty_selector": ".d_m_centre p",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "首个人物照片卡",
                "end_anchor": "末个人物照片卡",
                "include_selectors": [".ld_list li a[href]", ".d_m_centre"],
                "exclude_selectors": ["装饰图片", "我的分工", "我的简历", "导航与页脚"],
            },
        },
        "api": {"enabled": False, "reason": "人物照片卡及详情页均有明确静态HTML姓名、职务字段"},
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
        if "ld_list" in classes:
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
    if "/hfpc/ldxx/20" not in parsed.path or not parsed.path.endswith(".shtml"):
        return ""
    return resolved


def _extract_detail(name: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".d_m_centre")
    if scope is None:
        return "", ""
    name_node = scope.select_one("h2")
    duty_node = scope.select_one("p")
    detail_name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node is not None else ""
    duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
    return (duty, duty) if detail_name == name and duty else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".ld_list li a[href]"):
        if _is_hidden(link):
            continue
        name_node = link.select_one("p")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node is not None else ""
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
                "parser": "custom_xinjiang_health_portrait_directory_details_v1",
                "selector_summary": ".ld_list照片卡HTML姓名；详情.d_m_centre p职务/h2姓名",
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
