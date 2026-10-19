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
    "rule_id": "1316",
    "domain": "jyj.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "category_data_url_leader_h3_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "dynamic_subpage_list",
    "collector": "raw_http",
    "parser": "page_inline_category_data_url_leader_h3_role_v1",
    "category_link_selector": "a[data-url]",
    "category_text_anchor": "机关简介",
    "leader_card_selector": ".leaderList ul.leader1 > li",
    "leader_heading_selector": ".ldjj_right_box h3",
    "duty_selector": ".ldjj_right_box h3 i",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物卡片无详情链接；详情页必须留空，不能把机关简介栏目页写入详情",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩字段中的排版空白，不改变职务语义。"""
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


def extract_name_from_heading(heading: object) -> str:
    """从h3直接文本节点取得姓名，排除内部i职务节点。"""
    if not hasattr(heading, "contents"):
        return ""
    for child in heading.contents:
        if isinstance(child, str) and clean_text(child):
            return clean_name(child)
    text = clean_text(heading.get_text(" ", strip=True))
    match = re.match(r"^([\u3400-\u9fff·]{2,5})", text)
    return clean_name(match.group(1) if match else "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """发现官方机关简介子页，并按领导卡片DOM顺序提取姓名与职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    source_url = str(page_rule.get("url", "")) or final_url
    content_url = discover_content_url(html, final_url or source_url, page_rule)
    if not content_url:
        return []

    result = fetch_by_raw_requests(content_url, timeout=40)
    soup = BeautifulSoup(result.html, "html.parser")
    card_selector = str(page_rule.get("leader_card_selector", ""))
    heading_selector = str(page_rule.get("leader_heading_selector", ""))
    duty_selector = str(page_rule.get("duty_selector", ""))
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(card_selector):
        heading = card.select_one(heading_selector)
        duty_node = card.select_one(duty_selector)
        if heading is None or duty_node is None:
            continue
        name = extract_name_from_heading(heading)
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；category=机关简介 a[data-url]；"
                    "card=.leaderList ul.leader1 > li；name=h3 direct text；duty=h3 i"
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
