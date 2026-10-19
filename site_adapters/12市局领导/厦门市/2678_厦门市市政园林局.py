from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2678",
    "page_type": "人物列表完整页",
    "structure_group": "xm_municipal_garden_leader_dropdown_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_municipal_garden_leader_dropdown_v2",
    "leader_region_selector": ".leader_name_list .dropdown_menu",
    "name_selector": "li a[href] > span",
    "duty_selector": "li a[href] > p",
    "detail_link_selector": "li a[href]",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "页面同时含面包屑和简介文本；只解析领导下拉目录中的姓名、职务和一一对应链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导下拉目录顺序提取姓名、原始职务和详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政园林局领导下拉目录")
    records: list[object] = []
    seen: set[str] = set()
    for link in region.select("li a[href]"):
        name_node = link.select_one(":scope > span")
        duty_node = link.select_one(":scope > p")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        evidence = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("领导目录项缺少有效姓名或职务")
        if name in seen:
            raise RuntimeError(f"领导目录姓名重复：{name}")
        detail_url = urljoin(page_rule["url"], str(link.get("href") or ""))
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="" if detail_url == page_rule["url"] else detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导下拉目录中未提取到人物")
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
