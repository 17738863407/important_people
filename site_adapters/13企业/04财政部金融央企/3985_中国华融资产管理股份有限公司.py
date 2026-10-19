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
    "rule_id": "3985", "domain": "www.famc.citic", "page_type": "领导团队履历卡片",
    "structure_group": "citic_financial_asset_leader_team", "reuse_scope": "famc_citic_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_famc_citic_leader_team_v1", "leader_region_selector": ".inner_txt",
    "name_selector": ".lead_team .title-red", "duty_selector": ".lead_team .title-explain",
    "content_scope": {"include_selectors": [".inner_txt"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "主表沿用原中国华融名称而官网已更名中国中信金融资产，结果机构仍按主表注入并记录复核",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": ".inner_txt > .lead_team", "name_selector": ".title-red", "duty_selector": ".title-explain"}},
}


def normalize_text(value: str) -> str:
    """清理领导卡片字段中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """直接读取领导卡片的姓名标题和独立职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".inner_txt > .lead_team"):
        name_node = card.select_one(".title-red")
        duty_node = card.select_one(".title-explain")
        raw_name = normalize_text(name_node.get_text(" ", strip=True)) if name_node else ""
        name = re.sub(r"(?:先生|女士)$", "", raw_name)
        duty = normalize_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "领导团队卡片姓名标题与独立职务字段",
        })
    if not rows:
        raise RuntimeError("领导团队卡片未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
