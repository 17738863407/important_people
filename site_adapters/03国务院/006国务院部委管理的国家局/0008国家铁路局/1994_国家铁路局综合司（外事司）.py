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
    "rule_id": "1994",
    "page_type": "人物列表完整页",
    "structure_group": "内设机构主要领导字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NraDepartmentMainLeaderParser_v2",
    "leader_region_selector": ".nsjg_wrap .list_main",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一区域另含部门职责和内设处室，必须以主要领导标题限定卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """定位主要领导卡片并动态抽取职务冒号姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_card = None
    for card in soup.select(".nsjg_wrap .list_main"):
        title = card.select_one(".mobile_list_titles2")
        if title and _clean_text(title.get_text(" ", strip=True)) == "主要领导":
            leader_card = card
            break
    if leader_card is None:
        raise RuntimeError("未找到标题为主要领导的机构卡片")

    text_node = leader_card.select_one(".mobile_list_text1")
    evidence = _clean_text(text_node.get_text(" ", strip=True)) if text_node else ""
    match = re.fullmatch(r"(?P<duty>[^：:]+)\s*[：:]\s*(?P<name>[\u4e00-\u9fff·\s]{2,8})", evidence)
    if not match:
        raise RuntimeError("主要领导卡片未解析到职务冒号姓名")
    name = re.sub(r"\s+", "", match.group("name"))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
        raise RuntimeError("主要领导姓名格式异常")
    return [
        {
            "name": name,
            "duty": _clean_text(match.group("duty")),
            "evidence": _clean_text(match.group("duty")),
            "detail_url": "",
            "parser": PAGE_RULE["parser"],
            "selector_summary": ".nsjg_wrap .list_main；主要领导标题；.mobile_list_text1",
        }
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
