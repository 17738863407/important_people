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
    "rule_id": "0185",
    "page_type": "人物目录详情页",
    "structure_group": "chengdu_gov_leader_onclick_directory",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "cdzj_leader_directory_detail_v1",
    "leader_region_selector": "div.main_r div.html008 ul.list > li.myflex",
    "name_selector": "div.cont",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "列表详情链接位于 onclick；姓名与原始职务须在详情页交叉验证",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写语义内容。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _clean_name(value: str) -> str:
    """姓名字段允许清除由网页排版产生的字间空格。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _extract_detail_url(onclick: str, final_url: str) -> str:
    """从当前列表项的 window.open 调用中动态提取人物详情页。"""
    match = re.search(r"window\.open\(\s*['\"]([^'\"]+)['\"]", onclick)
    if not match:
        return ""
    detail_url = urljoin(final_url, match.group(1))
    parsed_entry = urlparse(final_url)
    parsed_detail = urlparse(detail_url)
    if parsed_detail.netloc != parsed_entry.netloc:
        return ""
    if not re.fullmatch(r"/gkml/ldcy/\d+\.shtml", parsed_detail.path):
        return ""
    return detail_url


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """从人物详情页的稳定标题和职务字段取得姓名、原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("#part_03 .blk01 h1")
    font_node = soup.select_one("#part_03 #myFont")
    if name_node is None or font_node is None:
        return "", ""

    detail_name = _clean_name(name_node.get_text(" ", strip=True))
    paragraphs = font_node.select(":scope > p")
    duty = ""
    for index, paragraph in enumerate(paragraphs[:-1]):
        label = _clean_text(paragraph.get_text(" ", strip=True)).rstrip("：:")
        if label == "职务":
            duty = _clean_text(paragraphs[index + 1].get_text(" ", strip=True))
            break
    return detail_name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表 DOM 顺序抓取并核验每个动态人物详情页。"""
    from crawler_core.fetcher import fetch_by_chrome_debug
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    list_items = soup.select(page_rule["leader_region_selector"])
    if not list_items:
        raise RuntimeError("领导成员列表选择器未命中")

    records: list[object] = []
    seen_detail_urls: set[str] = set()
    for source_order, item in enumerate(list_items, start=1):
        name_node = item.select_one(page_rule["name_selector"])
        list_name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        if not re.fullmatch(r"[一-鿿·]{2,8}", list_name):
            raise RuntimeError(f"第 {source_order} 个列表项姓名无效：{list_name or '空'}")

        detail_url = _extract_detail_url(str(item.get("onclick", "")), final_url)
        if not detail_url or detail_url in seen_detail_urls:
            raise RuntimeError(f"第 {source_order} 个列表项详情链接无效或重复")
        seen_detail_urls.add(detail_url)

        detail_result = fetch_by_chrome_debug(detail_url, timeout=60)
        detail_name, duty = _extract_detail_fields(detail_result.html)
        if detail_name != list_name:
            raise RuntimeError(
                f"第 {source_order} 个详情页姓名不一致：列表={list_name}，详情={detail_name or '空'}"
            )
        if not duty:
            raise RuntimeError(f"第 {source_order} 个详情页未取得职务：{detail_url}")

        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=list_name,
                duty=duty,
                detail_url=detail_url,
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
