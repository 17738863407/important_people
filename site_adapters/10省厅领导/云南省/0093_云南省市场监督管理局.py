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
    "rule_id": "0093",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_market_supervision_directory_profiles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_yunnan_market_supervision_directory_profiles_v1",
    "leader_region_selector": "div.pull-right.ld-left",
    "name_selector": "div.ld-top a[href], ul.ld-list a[href]",
    "duty_selector": "详情div.ld-p div.v_news_content首个非空p中的现任句或党员后现职片段",
    "detail_link_selector": "div.ld-top a[href], ul.ld-list a[href]",
    "content_scope": {
        "start_anchor": "主要领导姓名链接",
        "end_anchor": "其他领导末个姓名链接",
        "include_selectors": ["div.ld-top a[href]", "ul.ld-list a[href]", "div.ld-p div.v_news_content p"],
        "exclude_selectors": ["个人属性前缀", "其他正文", "导航与页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.ld-top a[href], ul.ld-list a[href]",
        "detail_name_selector": "div.ld-name",
        "detail_duty_selector": "div.ld-p div.v_news_content首个非空p中的现任句或党员后现职片段",
        "detail_content_selector": "div.ld-p div.v_news_content",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页把个人属性与现职写在同一简介段；优先提取当前人物完整现任句，否则以中共党员后的明确文本分隔取得现职片段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.pull-right.ld-left",
            "name_selector": "div.ld-top a[href], ul.ld-list a[href]",
            "duty_selector": "详情简介段当前人物现任句或党员后现职片段",
            "detail_link_selector": "姓名链接",
            "content_scope": {
                "start_anchor": "主要领导姓名链接",
                "end_anchor": "其他领导末个姓名链接",
                "include_selectors": ["div.ld-top a[href]", "ul.ld-list a[href]", "div.ld-p div.v_news_content p"],
                "exclude_selectors": ["个人属性前缀", "其他正文", "导航与页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML目录和人物详情简介直接提供姓名与现职文本"},
    },
}


def _clean_text(value: str) -> str:
    text = " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    return re.sub(r"(?<=[\u4e00-\u9fff，、])\s+(?=[\u4e00-\u9fff，、])", "", text)


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _clean_duty_evidence(value: str) -> str:
    """清理现职文本中的固定引导词、独立状态标记和纯句末句号。"""
    text = _clean_text(value)
    text = re.sub(r"^现任\s*", "", text)
    text = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", text)
    text = re.sub(r"[。．]\s*$", "", text)
    return _clean_text(text)


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "ld-left" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    if resolved.split("#", 1)[0].rstrip("/") == base_url.split("#", 1)[0].rstrip("/"):
        return ""
    parsed = urlparse(resolved)
    return resolved if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _extract_detail(list_name: str, detail_html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("div.ld-name")
    name = _clean_name(name_node.get_text(" ", strip=True)) if name_node is not None else list_name
    if not name:
        return "", "", ""
    profile = ""
    for paragraph in soup.select("div.ld-p div.v_news_content p"):
        profile = _clean_text(paragraph.get_text(" ", strip=True))
        if profile:
            break
    if not profile:
        return "", "", ""
    current_match = re.search(r"现任[^。]*。", profile)
    if current_match is not None:
        evidence = _clean_duty_evidence(current_match.group(0))
        return name, evidence, evidence
    duty_match = re.search(r"中共党员[，,]\s*([^。]+。)", profile)
    if duty_match is not None:
        evidence = _clean_duty_evidence(duty_match.group(1))
        return name, evidence, evidence
    return "", "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.ld-top a[href], ul.ld-list a[href]"):
        if _is_hidden(link):
            continue
        list_name = _clean_name(link.get_text(" ", strip=True))
        detail_url = _detail_url(base_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,30}", list_name) or not detail_url or list_name in seen:
            continue
        try:
            response = session.get(detail_url, timeout=30, headers={"Referer": base_url})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            name, duty, evidence = _extract_detail(list_name, response.text)
        except requests.RequestException:
            name, duty, evidence = list_name, "", ""
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_yunnan_market_supervision_directory_profiles_v1",
                "selector_summary": "目录姓名链接；详情ld-name及简介段现任句/党员后现职片段",
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
