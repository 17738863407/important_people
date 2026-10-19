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
    "rule_id": "1838",
    "page_type": "人物表格卡片页",
    "structure_group": "不规范嵌套表格的直接行字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NingboCppccDirectRowsLeaderTableParser_v2",
    "leader_region_selector": ".article table",
    "risk_flag": "后续人物表被嵌套进前一表，必须仅读取每张表自身直接tbody行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一网页排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """逐表读取自身直接行，避免父表聚合嵌套的后续人物。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for table in soup.select(rule["leader_region_selector"]):
        own_rows = table.select(":scope > tbody > tr")
        if len(own_rows) < 2:
            continue
        duty_node = own_rows[0].select_one("strong")
        name_node = own_rows[1].select_one("strong")
        evidence = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not evidence or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".article table自身直接tbody前两行的strong职务与姓名",
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
