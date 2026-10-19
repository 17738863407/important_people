from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0565",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_fgw_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_fgw_leader_cards_v2",
    "leader_region_selector": ".main .top_box",
    "name_selector": "li > p > a[href]",
    "duty_selector": "li > p:not(:has(a))",
    "detail_link_selector": "li > p > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "li > p > a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "人物姓名存在字距空格，职务与姓名分别位于相邻独立段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并卡片文本空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导卡片DOM顺序提取姓名、原始职务与详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".main .top_box")
    if len(regions) != 1:
        raise RuntimeError(f"领导卡片区域数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for card in regions[0].select(":scope > ul > li"):
        name_link = card.select_one("p > a[href]")
        duty_nodes = [paragraph for paragraph in card.select(":scope > p") if paragraph.select_one("a") is None]
        if name_link is None:
            continue
        if len(duty_nodes) != 1:
            raise RuntimeError(f"领导卡片职务段数量异常：{len(duty_nodes)}")
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True)))
        evidence = clean_text(duty_nodes[0].get_text(" ", strip=True))
        detail_url = urljoin(final_url, name_link.get("href", "").strip())
        parts = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导卡片姓名或职务异常：{name} {evidence}")
        if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"领导卡片详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"领导卡片姓名或链接重复：{name} {detail_url}")
        seen_names.add(name)
        seen_links.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导卡片区域没有人物记录")
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
