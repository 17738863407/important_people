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


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介卡片原序提取姓名和当前职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".ldlist.fixed")
    if not cards:
        raise RuntimeError("未找到领导简介卡片 .ldlist.fixed")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in cards:
        name_node = card.select_one(".info h2")
        duty_node = card.select_one(".info .position")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip("，,。；; ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".ldlist.fixed领导卡片原序；h2姓名、p.position完整职务；领导区委员同样保留"})
        seen.add(name)
    if not rows:
        raise RuntimeError("领导简介卡片未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4526", "domain": "www.chinagscourt.gov.cn", "page_type": "领导简介卡片",
    "structure_group": "gansu_high_court_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_gansu_high_court_leader_cards_v1",
    "leader_region_selector": ".ldlist.fixed", "name_selector": ".info h2", "duty_selector": ".info .position",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "risk_flag": "仅解析领导简介卡片；卡片内委员及法官资格等网页职务原文均保留",
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
