from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0513", "page_type": "多人物详情合并页", "structure_group": "xian_education_label_value_leaders_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_education_label_value_leaders_v2",
    "leader_region_selector": ".leader", "name_selector": ".pure-g内姓名标签相邻.txt", "duty_selector": ".pure-g内职务标签相邻.txt",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "合并卡片同时含职责、简历和时间，必须只取姓名与职务明确字段；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def clean_label(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value)).rstrip("：:")


def clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留其前面的具体兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", clean_text(value)).strip()


def field_value(card: object, keyword: str) -> str:
    for row in card.select(".pure-g"):
        label = row.select_one(".tnm"); value = row.select_one(".txt")
        if label and value and clean_label(label.get_text(" ", strip=True)) == keyword:
            return clean_text(value.get_text(" ", strip=True))
    return ""


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser"); cards = soup.select(".leader > .pure-g")
    names = [re.sub(r"\s+", "", field_value(card, "姓名")) for card in cards]
    if cards and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try: soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc: raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); regions = [region for region in soup.select(".leader") if region.select(":scope > .pure-g")]
    if not regions: raise RuntimeError("未找到领导合并区域")
    records: list[object] = []; seen_names: set[str] = set()
    for card in regions[0].select(":scope > .pure-g"):
        name = re.sub(r"\s+", "", field_value(card, "姓名")); evidence = clean_duty_evidence(field_value(card, "职务"))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence: raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
        if name in seen_names: raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records: raise RuntimeError("领导合并页没有可验证人物字段")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
