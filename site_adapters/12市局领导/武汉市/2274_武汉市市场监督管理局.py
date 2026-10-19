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
    "rule_id": "2274", "page_type": "人物列表完整页", "structure_group": "wuhan_market_supervision_leader_cards_v3",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_market_supervision_leader_cards_v3",
    "leader_region_selector": ".article .container > .card", "name_selector": ".card-name", "duty_selector": ".card-content内当前人物现任句",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "页面已改为姓名标题与简介正文卡片；只在当前人物卡片内提取完整现任句，排除简历属性及全页其他文本。",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select(".card .card-name")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    cards = soup.select(str(page_rule["leader_region_selector"]))
    if not cards:
        raise RuntimeError("领导信息页没有可验证人物卡片")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        name_node = card.select_one(str(page_rule["name_selector"]))
        content = card.select_one(".card-content")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        content_text = clean_text(content.get_text(" ", strip=True) if content else "")
        if name and name not in re.sub(r"\s+", "", content_text):
            raise RuntimeError(f"领导卡片标题与简介姓名不一致：{name}")
        current_match = re.search(r"现任[^。]*。", content_text)
        evidence = re.sub(r"^现任", "", current_match.group(0)).rstrip("。") if current_match else ""
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务异常：{name} {evidence}")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
