from __future__ import annotations

import sys
import re
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
    "rule_id": "4579",
    "page_type": "检察院领导表格卡片",
    "structure_group": "chongqing_procuratorate_leader_tables_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "leader_tables",
    "parser": "page_chongqing_procuratorate_leader_tables_v1",
    "leader_region_selector": "table.sk20.xk20",
    "name_selector": "a.blue18c[href]",
    "duty_selector": "td.b16.hg190",
    "detail_link_selector": "a.blue18c[href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析领导表格；检察委员会委员、专职委员等委员类人物以及网页同列展示的职务职级均按原序完整保留。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导表格原序提取，包含委员类人物与完整职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table.sk20.xk20")
    if not tables:
        raise RuntimeError("未找到领导表格 table.sk20.xk20")
    rows: list[dict[str, str]] = []
    for table in tables:
        link = table.select_one("a.blue18c[href]")
        duty_node = table.select_one("td.b16.hg190")
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True) if link else "")
        raw_duty = re.sub(r"[\s\u00a0\u3000]+", "", duty_node.get_text(" ", strip=True) if duty_node else "")
        evidence = raw_duty.strip("，,、；;。 ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if not evidence:
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": urljoin(final_url, str(link.get("href") or "")), "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "table.sk20.xk20按a.blue18c姓名和td.hg190职务原序完整提取"})
    if not rows:
        raise RuntimeError("领导表格未提取到人物职务")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
