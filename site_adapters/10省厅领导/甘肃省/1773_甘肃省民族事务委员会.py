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
    "rule_id": "1773",
    "domain": "mzsw.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_ethnic_affairs_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_ethnic_affairs_leader_cards_v1",
    "leader_region_selector": ".lingdaozhichuang li",
    "field_selector": "p",
    "name_label": "姓名",
    "duty_label": "职务",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "普通HTTP返回412防护页；领导卡片含简介、分工和分管处室，须仅提取姓名与职务标签字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def field_value(lines: list[str], label: str) -> str:
    """从明确标签字段中取得冒号后的原始值。"""
    compact_label = re.sub(r"\s+", "", label)
    for line in lines:
        compact = re.sub(r"[\s\u3000\u00a0]+", "", line)
        match = re.fullmatch(rf"{re.escape(compact_label)}[：:](.+)", compact)
        if match is not None:
            return match.group(1).strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后领导卡片DOM顺序抽取明确姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        lines = [clean_text(node.get_text(" ", strip=True)) for node in item.select(str(page_rule["field_selector"]))]
        name = field_value(lines, str(page_rule["name_label"]))
        evidence = field_value(lines, str(page_rule["duty_label"]))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
            }
        )
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
