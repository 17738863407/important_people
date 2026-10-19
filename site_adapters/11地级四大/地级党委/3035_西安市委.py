from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3035",
    "page_type": "职务分组名单页",
    "structure_group": "xian_party_standing_committee_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_xian_party_standing_committee_v2",
    "leader_region_selector": ".dian1 li",
    "name_selector": "lable",
    "duty_selector": "span",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名节点标签为站点原生拼写lable；部分二字姓名使用letter-spacing及格式字符",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(text: str) -> str:
    cleaned = "".join(ch for ch in (text or "") if unicodedata.category(ch) != "Cf")
    return "".join(cleaned.split())


def _clean_duty(text: str) -> str:
    return "".join((text or "").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析西安市委常委名单。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for item in soup.select(".dian1 li"):
        duty_node = item.select_one("span")
        name_node = item.select_one("lable")
        duty = _clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not name or not duty:
            continue
        records.append(
            {
                "organization": str(rule.get("organization") or ""),
                "url": str(rule.get("url") or "") or base_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": rule["parser"],
                "selector_summary": "strategy=custom_parse_page；leader=.dian1 li；name=lable；duty=span",
            }
        )
    return records


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
