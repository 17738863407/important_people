from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0205",
    "page_type": "人物列表完整页",
    "structure_group": "cgs_left_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".ju_ld_s",
    "name_selector": "p.ld_name a",
    "duty_selector": "p.ld_intro",
    "detail_link_selector": "p.ld_name a[href]",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "首张卡片链接等于入口页，其余卡片指向独立人物简介",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理网页排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按局领导区域主卡片与列表卡片的页面顺序提取。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".ju_ld_s")
    if scope is None:
        raise RuntimeError("未找到局领导区域")
    cards = []
    main_card = scope.select_one(".ld_1")
    if main_card is not None:
        cards.append(main_card)
    cards.extend(scope.select("ul.ld_2 > li"))

    entry_url = urldefrag(urljoin(final_url, ""))[0].rstrip("/")
    records: list[PersonRecord] = []
    for card in cards:
        name_link = card.select_one("p.ld_name a")
        duty_node = card.select_one("p.ld_intro")
        if name_link is None or duty_node is None:
            continue
        name = _clean_text(name_link.get_text(" ", strip=True)).replace(" ", "")
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        href = str(name_link.get("href") or "")
        candidate = urldefrag(urljoin(final_url, href))[0] if href else ""
        detail_url = "" if candidate.rstrip("/") == entry_url else candidate
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="ju_ld_s主卡片及ld_2列表内姓名职务",
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
