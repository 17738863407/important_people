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
    "rule_id": "3404",
    "page_type": "人物目录详情页",
    "structure_group": "wuhan_natural_resources_home_discovered_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "directory_detail",
    "collector": "static_http",
    "parser": "wuhan_natural_resources_home_discovered_leaders_v2",
    "leader_region_selector": ".article-box table.mytable a[href]",
    "name_selector": ".leader.tc h4",
    "duty_selector": ".leader.tc p",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "市级领导列表按卡片顺序提取，并逐页核验姓名、原始职务和详情地址",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页排版空白，不改写字段语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _validate_detail_url(href: str, leader_index_url: str) -> str:
    detail_url = urljoin(leader_index_url, href)
    index = urlparse(leader_index_url)
    detail = urlparse(detail_url)
    if detail.netloc != index.netloc:
        return ""
    if not re.fullmatch(r"/zwgk_18/fdzdgk/ldxx/\d{6}/t\d+_\d+\.shtml", detail.path):
        return ""
    return detail_url


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".leader.tc h4")
    duty_node = soup.select_one(".leader.tc p")
    if name_node is None or duty_node is None:
        return "", ""
    name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
    duty = _clean_text(duty_node.get_text(" ", strip=True))
    if not re.fullmatch(r"[一-鿿·]{2,8}", name) or not duty:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市级领导列表卡片顺序提取，并逐页核验姓名、职务和详情地址。"""
    from crawler_core.fetcher import fetch_by_raw_requests
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html, "html.parser")
    expected = urlparse(page_rule["url"])
    actual = urlparse(final_url)
    if actual.netloc != expected.netloc or actual.path.rstrip("/") != expected.path.rstrip("/"):
        raise RuntimeError("市级领导入口发生非预期跳转")

    entry_text = _clean_text(entry_soup.get_text(" ", strip=True))
    if page_rule["organization"] not in entry_text:
        raise RuntimeError("市级领导入口缺少机构归属标识")

    leader_index_url = final_url
    links = entry_soup.select(page_rule["leader_region_selector"])
    if not links:
        raise RuntimeError("市级领导列表未命中人物链接")

    records: list[object] = []
    seen_names: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        detail_url = _validate_detail_url(str(link.get("href", "")), leader_index_url)
        if not detail_url:
            raise RuntimeError(f"第 {source_order} 个市级人物详情链接无效")
        list_lines = [
            _clean_text(line)
            for line in link.get_text("\n", strip=True).splitlines()
            if _clean_text(line)
        ]
        if len(list_lines) != 2:
            raise RuntimeError(f"第 {source_order} 个市级列表项字段数量异常")
        list_name = re.sub(r"\s+", "", list_lines[0])
        list_duty = list_lines[1]

        detail_result = fetch_by_raw_requests(detail_url, timeout=60)
        name, detail_duty = _extract_detail_fields(detail_result.html)
        if name != list_name or name in seen_names:
            raise RuntimeError(
                f"第 {source_order} 个详情姓名不一致或重复：列表={list_name}，详情={name or '空'}"
            )
        duty_parts = [part for part in re.split(r"[、，,]", list_duty) if part]
        if not duty_parts or any(part not in detail_duty for part in duty_parts):
            raise RuntimeError(f"第 {source_order} 个列表职务无法由详情页原文验证")
        if not _validate_detail_url(detail_result.final_url, leader_index_url):
            raise RuntimeError(f"第 {source_order} 个详情最终地址不符合市级领导路径")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=list_duty,
                detail_url=detail_result.final_url,
                evidence=list_duty,
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
