from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2345",
    "page_type": "人物目录详情页",
    "structure_group": "hefei_agency_affairs_leader_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "hefei_agency_affairs_leader_detail_v1",
    "leader_region_selector": "a[href*='/jgsz/ldjs/'][href$='.html']",
    "name_selector": "h1.wztit",
    "duty_selector": ".wzcon.j-fontContent p",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "栏目需浏览器渲染；详情仅取姓名开头简介段中的完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写原始语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _validate_detail_url(href: str, entry_url: str) -> str:
    """只接受入口页动态提供的同域领导介绍详情地址。"""
    detail_url = urljoin(entry_url, href)
    entry = urlparse(entry_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/jgsz/ldjs/\d+\.html", detail.path):
        return ""
    return detail_url


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """从详情标题和对应简介段提取姓名及完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("h1.wztit")
    region = soup.select_one(".wzcon.j-fontContent")
    if name_node is None or region is None:
        return "", ""

    name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
    if not re.fullmatch(r"[一-鿿·]{2,8}", name):
        return "", ""
    duties: list[str] = []
    for paragraph in region.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text.startswith(name):
            continue
        duty_match = re.search(r"现任[^。]*。", text)
        if duty_match:
            duties.append(duty_match.group(0))
    if len(duties) != 1:
        return "", ""
    return name, duties[0].removeprefix("现任").removesuffix("。").rstrip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按栏目DOM顺序动态发现链接并在线解析每个人物详情页。"""
    from crawler_core.fetcher import fetch_by_playwright
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    links = [
        link
        for link in soup.select(page_rule["leader_region_selector"])
        if _validate_detail_url(str(link.get("href", "")), final_url)
        and re.fullmatch(
            r"[一-鿿·]{2,8}",
            re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True))),
        )
    ]
    if not links:
        raise RuntimeError("机构领导详情链接选择器未命中")

    records: list[object] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        detail_url = _validate_detail_url(str(link.get("href", "")), final_url)
        if not detail_url or detail_url in seen_urls:
            raise RuntimeError(f"第 {source_order} 个详情链接无效或重复")
        list_name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[一-鿿·]{2,8}", list_name):
            raise RuntimeError(f"第 {source_order} 个栏目姓名无效：{list_name or '空'}")

        detail_result = fetch_by_playwright(detail_url, timeout=60)
        detail_name, duty = _extract_detail_fields(detail_result.html)
        if detail_name != list_name:
            raise RuntimeError(
                f"第 {source_order} 个详情姓名不一致：栏目={list_name}，详情={detail_name or '空'}"
            )
        if not duty or detail_name in seen_names:
            raise RuntimeError(f"第 {source_order} 个详情职务为空或姓名重复：{detail_name}")
        if not _validate_detail_url(detail_result.final_url, final_url):
            raise RuntimeError(f"第 {source_order} 个详情最终地址不符合栏目路径")

        seen_urls.add(detail_url)
        seen_names.add(detail_name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=detail_name,
                duty=duty,
                detail_url=detail_result.final_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
