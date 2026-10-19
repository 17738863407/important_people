from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_target_duty(value: str) -> str:
    value = re.sub(r"^现任", "", clean_text(value)).strip("，,。；; ")
    pieces = [clean_text(item).strip("，,。；; ") for item in re.split(r"[、，,；;]", value)]
    excluded = ("审判员", "法官")
    return "、".join(item for item in pieces if item and not any(term in item for term in excluded))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按高院领导卡片原序提取姓名和现任职务句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".r_list .slid-leader .leader-list")
    if not cards:
        raise RuntimeError("未找到高院领导卡片 .slid-leader .leader-list")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in cards:
        name_node = card.select_one("li.name")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        current = next((clean_text(p.get_text(" ", strip=True)) for p in card.select("li.note p") if clean_text(p.get_text(" ", strip=True)).startswith("现任")), "")
        duty = clean_target_duty(current)
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".slid-leader .leader-list卡片原序；li.name姓名、li.note中现任句；保留委员职务，仅剔除独立法官资格"})
        seen.add(name)
    if not rows:
        raise RuntimeError("高院领导卡片未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4528", "domain": "www.gdcourts.gov.cn", "page_type": "高院领导简介卡片",
    "structure_group": "guangdong_high_court_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_guangdong_high_court_leader_cards_v1",
    "leader_region_selector": ".r_list .slid-leader", "name_selector": ".leader-list li.name",
    "duty_selector": ".leader-list li.note p中现任句", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "locator_strategy": "custom_parse_page",
    "risk_flag": "同卡片含履历和现任句；只取现任句，领导卡片中的委员和专职委员职务保留，仅剔除独立法官资格",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
