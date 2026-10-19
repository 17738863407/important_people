from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2169",
    "page_type": "人物轮播卡片",
    "structure_group": "urumqi_people_congress_home_carousel_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "urumqi_people_congress_home_carousel_v2",
    "leader_region_selector": "#index_rightside .index_rightsum1 .leftLoop .bd > ul",
    "name_selector": "li dl dd strong",
    "duty_selector": "li dl dd p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "轮播脚本渲染后可能生成克隆节点，优先解析在线响应中的原始ul并按姓名去重",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按首页“领导介绍”原始轮播卡片顺序抽取姓名和完整职务文本。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for item in region.select(":scope > li"):
        duty_node = item.select_one("dl dd")
        name_node = duty_node.select_one("strong") if duty_node else None
        if duty_node is None or name_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,30}", name):
            continue
        text_parts = [_clean_text(text) for text in duty_node.stripped_strings]
        duty = _clean_text(" ".join(part for part in text_parts[1:] if part))
        if not duty:
            continue
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
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
