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
    "rule_id": "0650",
    "domain": "gbdsj.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_cards_name_role_link_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_leader_cards_name_role_link_v1",
    "leader_region_selector": ".BuConx .CusList",
    "leader_card_selector": "li",
    "name_selector": ".CusDiv h3 a",
    "duty_selector": ".CusDiv span",
    "detail_link_selector": ".CusDiv h3 a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "详情含简历和分工；依据仅取入口人物卡片独立职务节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩卡片字段中的排版空白并移除零宽字符。"""
    text = str(value or "").replace("\u200b", "")
    return re.sub(r"[\s\u3000\xa0\u2000-\u200a]+", " ", text).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物卡片DOM顺序提取姓名、职务和详情链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    card_selector = str(page_rule.get("leader_card_selector", ""))
    name_selector = str(page_rule.get("name_selector", ""))
    duty_selector = str(page_rule.get("duty_selector", ""))
    link_selector = str(page_rule.get("detail_link_selector", ""))
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in region.select(card_selector):
        name_node = card.select_one(name_selector)
        duty_node = card.select_one(duty_selector)
        link = card.select_one(link_selector)
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        href = str(link.get("href", "")).strip() if link is not None else ""
        detail_url = urljoin(final_url or source_url, href) if href else ""
        seen.add(name)
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
                    "strategy=custom_parse_page；region=.BuConx .CusList；card=li；"
                    "name=.CusDiv h3 a；duty=.CusDiv span；detail=name link"
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
