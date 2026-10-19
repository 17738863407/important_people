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
    "rule_id": "3429",
    "domain": "zsj.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_cards_two_paragraph_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_cards_two_paragraph_fields_v1",
    "leader_region_selector": ".leaderList",
    "leader_card_selector": "li a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "只解析领导列表双p强字段，排除导航、新闻和其他机构目录",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩卡片字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取双p强字段和人物链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select(str(page_rule.get("leader_card_selector", ""))):
        paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in link.select("p")]
        if len(paragraphs) < 2:
            continue
        duty = paragraphs[0]
        name = clean_name(paragraphs[1])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url or source_url, str(link.get("href", ""))),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.leaderList；card=li a[href]；"
                    "duty=p[1]；name=p[2]；detail=card_href"
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
