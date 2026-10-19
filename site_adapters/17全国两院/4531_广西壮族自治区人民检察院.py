from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4531",
    "page_type": "检察院领导卡片",
    "structure_group": "guangxi_procuratorate_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "leader_cards",
    "parser": "page_guangxi_procuratorate_leader_cards_v1",
    "leader_region_selector": ".pagebox",
    "name_selector": ".yld .xm",
    "duty_selector": ".yld .wz span",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "按领导卡片原序提取；职务证据取每张卡片简介中可定位的现任句，完整保留委员、检察员和检察官等级。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按当前入口页面的领导卡片顺序提取姓名及简介中的现任职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".pagebox")
    if region is None:
        raise RuntimeError("未找到领导卡片区域 .pagebox")
    rows: list[dict[str, str]] = []
    for card in region.select(".yld"):
        name_node = card.select_one(".xm")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        card_text = re.sub(r"[\s\u3000\xa0]+", "", card.get_text(" ", strip=True))
        current_match = re.search(r"现任([^。]+)", card_text)
        duty = current_match.group(1).strip("，,；;。 ") if current_match else ""
        if not duty:
            raise RuntimeError(f"领导卡片缺少可定位的现任职务：{name}")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".pagebox内.yld卡片按DOM原序提取.xm姓名及卡片简介现任句"})
    if not rows:
        raise RuntimeError("现行领导栏目未提取到目标领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
