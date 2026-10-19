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
    "rule_id": "1324",
    "page_type": "人物列表完整页",
    "structure_group": "xining_education_person_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "xining_education_person_cards_v2",
    "leader_region_selector": ".fdzdjg-content-box",
    "name_selector": ".person .name",
    "duty_selector": ".person .position",
    "detail_link_selector": ".person > a[href]",
    "detail_strategy": {"required": False, "mode": "list_embedded", "max_detail_links": 20},
    "risk_flag": "旧body范围过宽；仅解析机构简介领导盒内person卡片及一一对应详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理网页字段中的排版空白，不改变原始语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片的DOM顺序提取姓名、职务和真实详情页。"""
    from crawler_core.models import PersonRecord

    cards = BeautifulSoup(html or "", "html.parser").select(".fdzdjg-content-box .person")
    if not cards:
        raise RuntimeError("机构简介领导区域没有人物卡片")
    records: list[object] = []
    seen: set[str] = set()
    for card in cards:
        name_node = card.select_one(".name")
        duty_node = card.select_one(".position")
        link_node = card.select_one(":scope > a[href]")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = clean_text(link_node.get("href", "") if link_node else "")
        if re.fullmatch(r"[\u3400-\u9fff\U00020000-\U0002FA1F·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            raise RuntimeError(f"人物详情链接异常：{name} {href}")
        if name in seen:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=urljoin(final_url or page_rule["url"], href),
                evidence=evidence,
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
