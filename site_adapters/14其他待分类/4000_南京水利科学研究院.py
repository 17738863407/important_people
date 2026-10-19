from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4000", "page_type": "研究院现任领导卡片页", "structure_group": "nhri_current_leaders", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_nhri_current_leaders_v1",
    "leader_region_selector": "#现任领导list", "name_selector": ".ycxx .sp-1", "duty_selector": ".ycxx .sp-1", "detail_link_selector": ".ycxx a[href]",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "主体内容结束", "include_selectors": ["#现任领导list"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "dynamic_card_link"}, "risk_flag": "同页含历任院长；仅id为现任领导list的卡片列表可抽取。", "confidence": "high", "profile_reusable": False, "profile_judgement": "已核验卡片首行“职务 姓名”与详情链接一一对应。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#现任领导list", "name_selector": ".ycxx .sp-1", "duty_selector": ".ycxx .sp-1", "detail_link_selector": ".ycxx a[href]"}, "api": {"enabled": False, "reason": "当前HTML卡片结构完整"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从现任领导卡片的首行动态拆分职务和姓名。"""
    root = BeautifulSoup(html, "html.parser").select_one("#现任领导list")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    for card in root.select("li.xxlist"):
        line = clean_text(card.select_one(".ycxx .sp-1").get_text(" ", strip=True)) if card.select_one(".ycxx .sp-1") else ""
        match = re.match(r"(.+?)\s+([\u4e00-\u9fff]{2,4})$", line)
        if match is None:
            continue
        duty, name = clean_text(match.group(1)), match.group(2)
        link = card.select_one(".ycxx a[href]")
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"]) if link else "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": "#现任领导list .ycxx .sp-1"})
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
