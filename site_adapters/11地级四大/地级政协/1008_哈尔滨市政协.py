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
    "rule_id": "1008",
    "page_type": "人物卡片页",
    "structure_group": "表格卡片姓名职务双字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "HarbinCppccLeaderCardParser_v2",
    "leader_region_selector": "table.gegege",
    "name_selector": ".px14hei",
    "duty_selector": ".px14hei",
    "risk_flag": "卡片内链接均指向网站首页，不得作为人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按卡片DOM顺序读取姓名与职务两个强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(rule["leader_region_selector"]):
        fields = [_clean_text(node.get_text(" ", strip=True)) for node in card.select(rule["name_selector"])]
        fields = [field for field in fields if field]
        if len(fields) < 2:
            continue
        name = _clean_name(fields[0])
        evidence = fields[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": "table.gegege卡片内前两个.px14hei字段",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
