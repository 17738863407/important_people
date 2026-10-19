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
    "rule_id": "2534", "page_type": "人物列表完整页", "structure_group": "shenyang_water_labeled_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_water_labeled_cards_v2",
    "leader_region_selector": ".x-leader-info", "name_selector": "姓名职务标签font中职务起始边界之前",
    "duty_selector": "姓名职务标签font中局党组或二级巡视员锚点起始的原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名职务为连写字段；领导分工和办公电话不得混入，页面无独立详情链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片顺序解析唯一的“姓名职务”标签字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".x-leader-info")
    if not cards:
        raise RuntimeError("页面没有找到人物卡片")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        labeled_items = [
            item
            for item in card.select("li")
            if "姓名职务" in clean_text(item.select_one("span").get_text(" ", strip=True) if item.select_one("span") else "")
        ]
        if len(labeled_items) != 1:
            raise RuntimeError(f"人物卡片的姓名职务标签数量异常：{len(labeled_items)}")
        value_node = labeled_items[0].select_one("font")
        combined = clean_text(value_node.get_text(" ", strip=True) if value_node else "")
        marker = re.search(r"局党组|二级巡视员", combined)
        if marker is None or marker.start() <= 0:
            raise RuntimeError(f"姓名职务字段缺少职务起始锚点：{combined}")
        name = re.sub(r"\s+", "", combined[:marker.start()])
        evidence = clean_text(combined[marker.start():])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物卡片姓名或职务字段异常")
        if card.select_one("a[href]") is not None:
            raise RuntimeError(f"人物卡片出现未审计链接：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")
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
