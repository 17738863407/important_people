from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4532",
    "page_type": "省级法院人物卡片列表",
    "structure_group": "guizhou_high_court_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_guizhou_high_court_leader_cards_v1",
    "leader_region_selector": "ul.leader > li",
    "name_selector": "h4",
    "duty_selector": ".desc",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": True, "mode": "person_card_link"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "人物卡片按网页顺序；领导区域中的审判委员会委员、专职委员等委员职务和仅任委员者均保留；卡片链接为一一对应人物详情页。",
}


def clean_duty(value: str) -> str:
    """整理人物卡片职务分隔符，保留全部可验证领导职务。"""
    parts = [part.strip() for part in re.split(r"[、；;]", re.sub(r"\s+", "", value or "")) if part.strip()]
    return "、".join(parts)


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("ul.leader > li"):
        name_node = card.select_one("h4")
        duty_node = card.select_one(".desc")
        link = card.select_one("a[href]")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = clean_duty(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty,
            "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "ul.leader人物卡片；h4姓名；.desc完整职务；卡片详情链接",
        })
    if not rows:
        raise RuntimeError("ul.leader人物卡片未提取到合规领导记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
