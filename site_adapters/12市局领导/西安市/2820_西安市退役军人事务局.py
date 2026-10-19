from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2820", "page_type": "多人物详情合并页", "structure_group": "xian_veterans_label_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_veterans_label_cards_v2",
    "leader_region_selector": ".leader:first-of-type", "name_selector": "顶层.pure-g内姓名标签相邻.txt",
    "duty_selector": "顶层.pure-g内职务标签相邻.txt", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "合并人物卡片仅取姓名与职务明确标签字段；页面无独立人物链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def field_value(card: object, keyword: str) -> str:
    for row in card.select(".pure-g"):
        label, value = row.select_one(".tnm"), row.select_one(".txt")
        if label and value and re.sub(r"\s+", "", clean_text(label.get_text(" ", strip=True))).rstrip("：:") == keyword:
            return clean_text(value.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".leader")
    if not regions:
        raise RuntimeError(f"领导区域数量异常：{len(regions)}")
    records: list[object] = []
    seen: set[str] = set()
    for card in regions[0].find_all("div", class_="pure-g", recursive=False):
        name = re.sub(r"\s+", "", field_value(card, "姓名"))
        evidence = field_value(card, "职务")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
        if name in seen:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("机构领导页没有可验证人物字段")
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
