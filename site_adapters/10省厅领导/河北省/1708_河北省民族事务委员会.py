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
    "rule_id": "1708",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_ethnic_affairs_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_ethnic_affairs_leader_cards_v1",
    "leader_region_selector": ".page-right [v-if='bkid==1']",
    "name_selector": ".abox span:nth-of-type(1)",
    "duty_selector": ".abox span:nth-of-type(2)",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导之窗", "end_anchor": "机构设置", "include_selectors": [".page-right [v-if='bkid==1']"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "同页包含民委介绍、机构设置和委员单位；按v-if业务分组严格限定领导之窗",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".page-right [v-if='bkid==1']", "name_selector": ".abox span:nth-of-type(1)", "duty_selector": ".abox span:nth-of-type(2)", "detail_link_selector": "", "content_scope": {"start_anchor": "领导之窗", "end_anchor": "机构设置", "include_selectors": [".page-right [v-if='bkid==1']"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导之窗分组直接包含人物卡片"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导之窗卡片顺序提取前两个明确span字段。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".page-right [v-if='bkid==1']")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in scope.select(".abox") if scope else []:
        fields = card.select("span")
        if len(fields) < 2:
            continue
        name = re.sub(r"\s+", "", fields[0].get_text(" ", strip=True))
        duty = _clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_ethnic_affairs_leader_cards_v1", "selector_summary": "领导之窗v-if分组 .abox；前两个span为姓名、职务"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
