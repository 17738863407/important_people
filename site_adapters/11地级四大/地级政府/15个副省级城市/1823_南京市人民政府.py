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
    "rule_id": "1823",
    "page_type": "人物目录详情页",
    "structure_group": "nanjing_government_first_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "directory_detail",
    "collector": "static_http",
    "parser": "nanjing_government_first_leader_table_v2",
    "leader_region_selector": ".jgld .header_list > table:first-of-type a.t3[href]",
    "name_selector": ".right-cont .ld-name",
    "duty_selector": ".right-cont .doc-cont:first-of-type",
    "detail_link_selector": "a.t3[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "仅处理首个市政府领导表，按动态详情页核名并取完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写原始语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_evidence(value: str) -> str:
    """删除现任句的固定前缀及纯句末句号。"""
    evidence = re.sub(r"^现任\s*", "", _clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def _validate_detail_url(href: str, entry_url: str) -> str:
    """只接受当前页面动态提供的同域市政府领导详情地址。"""
    detail_url = urljoin(entry_url, href)
    entry = urlparse(entry_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/dzld/zfld/\d{6}/t\d+_\d+\.html", detail.path):
        return ""
    return detail_url


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """从人物详情的姓名节点和首个简介节点提取可回指字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".right-cont .ld-name")
    intro_node = soup.select_one(".right-cont .doc-cont")
    if name_node is None or intro_node is None:
        return "", ""
    name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
    intro = _clean_text(intro_node.get_text(" ", strip=True))
    duty_match = re.search(r"现任[^。]*。", intro)
    if not re.fullmatch(r"[一-鿿·]{2,8}", name) or duty_match is None:
        return "", ""
    return name, _clean_evidence(duty_match.group(0))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按首个领导表DOM顺序在线核验每个独立人物页。"""
    from crawler_core.fetcher import fetch_by_raw_requests
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(page_rule["leader_region_selector"])
    if not links:
        raise RuntimeError("市政府领导首表未命中人物链接")

    records: list[object] = []
    seen_names: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        text = _clean_text(link.get_text(" ", strip=True))
        parts = text.split()
        if len(parts) < 2:
            raise RuntimeError(f"第 {source_order} 个列表标题无法拆分姓名和职务")
        list_name = re.sub(r"\s+", "", "".join(parts[:-1]))
        detail_url = _validate_detail_url(str(link.get("href", "")), final_url)
        if not detail_url:
            raise RuntimeError(f"第 {source_order} 个详情链接无效")

        detail_result = fetch_by_raw_requests(detail_url, timeout=60)
        name, duty = _extract_detail_fields(detail_result.html)
        if name != list_name or name in seen_names:
            raise RuntimeError(
                f"第 {source_order} 个详情姓名不一致或重复：列表={list_name}，详情={name or '空'}"
            )
        if not _validate_detail_url(detail_result.final_url, final_url):
            raise RuntimeError(f"第 {source_order} 个详情最终地址不符合领导路径")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
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
