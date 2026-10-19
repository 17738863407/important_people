from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def compact_text(text: str) -> str:
    """拼合由页面换行拆开的同一字段文本。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受页面强结构姓名首行中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.people.com.cn",
        "page_type": "人物列表完整页",
        "structure_group": "people_daily_leader_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_multiline_name_duty",
        "collector": "static_http",
        "parser": "page_people_daily_leader_cards_v1",
        "leader_region_selector": ".p4_content",
        "name_selector": ".peopleList li p first line",
        "duty_selector": ".peopleList li p lines after name before link",
        "detail_link_selector": ".peopleList li p a[href]",
        "content_scope": {
            "include_selectors": [".p4_content"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "direct_card_link",
            "detail_link_selector": "p a[href]",
            "candidate_links": [],
        },
        "risk_flag": "verified_multiline_duty_cards",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".p4_content",
                "item_selector": ".peopleList li",
                "detail_link_selector": "p a[href]",
            },
            "api": {"enabled": False, "reason": "静态HTML人物卡片已直接包含姓名、完整职务和详情链接"},
        },
    }


def text_segments_before_link(paragraph: Tag) -> list[str]:
    """依次取得人物段落中详情链接之前的可见文本行。"""
    segments: list[str] = []
    for text_node in paragraph.find_all(string=True):
        if text_node.find_parent("a") is not None:
            continue
        text = compact_text(str(text_node))
        if text:
            segments.append(text)
    return segments


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片原始顺序抽取姓名、完整职务及真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".p4_content")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select(".peopleList li"):
        paragraph = item.select_one("p")
        detail_link = item.select_one("p a[href]")
        if paragraph is None:
            continue
        segments = text_segments_before_link(paragraph)
        if len(segments) < 2:
            continue
        name = segments[0]
        duty = "".join(segments[1:]).strip(" ：:，,。.")
        if not is_name(name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = ""
        if detail_link is not None:
            detail_url = urljoin(final_url, str(detail_link.get("href", "")))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.p4_content；item=.peopleList li；fields=p text before detail link",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3559"
    main(rule_id_value)
