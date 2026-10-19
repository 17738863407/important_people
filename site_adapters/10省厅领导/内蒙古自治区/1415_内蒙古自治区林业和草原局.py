from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1415",
    "domain": "lcj.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "category_data_url_detail_heading_name_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "dynamic_subpage_list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_category_data_url_detail_heading_name_role_v1",
    "category_link_selector": "a[data-url]",
    "category_text_anchor": "机关简介",
    "leader_region_selector": ".leaderList",
    "detail_link_selector": "ul.leader1 a[href], ul.leader2 a[href]",
    "detail_name_selector": ".fly_title_ldxm",
    "detail_strategy": {"required": True, "mode": "detail_heading_strong_fields"},
    "risk_flag": "入口首张卡片无可用姓名文本；须逐条详情读取h3直接职务文本和.fly_title_ldxm姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩字段中的排版空白，不添加或替换职务标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def discover_content_url(html: str, final_url: str, page_rule: dict[str, object]) -> str:
    """按入口目录文本锚点动态发现官方机关简介子页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    anchor = str(page_rule.get("category_text_anchor", ""))
    selector = str(page_rule.get("category_link_selector", ""))
    for link in soup.select(selector):
        if clean_text(link.get_text(" ", strip=True)) != anchor:
            continue
        data_url = str(link.get("data-url", "")).strip()
        if data_url:
            return urljoin(final_url, data_url)
    return ""


def extract_direct_text(node: object) -> str:
    """合并节点直接文本，排除内部姓名标签。"""
    if not hasattr(node, "contents"):
        return ""
    parts = [clean_text(child) for child in node.contents if isinstance(child, str) and clean_text(child)]
    return clean_text(" ".join(parts))


def fetch_detail_record(
    detail_url: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> tuple[str, str]:
    """在线读取详情h3中的姓名和直接职务强字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    name_node = soup.select_one(str(page_rule.get("detail_name_selector", "")))
    if name_node is None or name_node.parent is None:
        return "", ""
    name = clean_name(name_node.get_text(" ", strip=True))
    duty = extract_direct_text(name_node.parent)
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """发现官方机关简介子页，并按入口详情链接顺序读取人物强字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    source_url = str(page_rule.get("url", "")) or final_url
    content_url = discover_content_url(html, final_url or source_url, page_rule)
    if not content_url:
        return []

    result = fetch_by_raw_requests(content_url, timeout=40)
    soup = BeautifulSoup(result.html, "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    selector = str(page_rule.get("detail_link_selector", ""))
    for source_order, link in enumerate(region.select(selector), start=1):
        detail_url = urljoin(result.final_url or content_url, str(link.get("href", "")))
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        try:
            name, duty = fetch_detail_record(detail_url, page_rule, source_order)
        except Exception:
            continue
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen_names:
            continue

        seen_names.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；category=机关简介 a[data-url]；"
                    "links=.leaderList leader1+leader2 a；detail name=.fly_title_ldxm；"
                    "duty=parent h3 direct text"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
