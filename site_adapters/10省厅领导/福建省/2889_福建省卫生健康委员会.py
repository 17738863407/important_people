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
    "rule_id": "2889",
    "domain": "wjw.fj.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "fujian_health_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_health_leader_table_v1",
    "leader_region_selector": ".TRS_Editor table",
    "row_selector": "tr",
    "name_column_index": 0,
    "duty_column_index": 1,
    "detail_link_selector": "td:first-child a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_table_name_links",
    },
    "risk_flag": "正文表格首行为表头；须按表格行序提取姓名、职务和姓名单元格人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文表格原始行序抽取姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(str(page_rule["leader_region_selector"]))
    if table is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for tr in table.select(str(page_rule["row_selector"])):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        name = clean_name(cells[int(page_rule["name_column_index"])].get_text(" ", strip=True))
        evidence = clean_text(cells[int(page_rule["duty_column_index"])].get_text(" ", strip=True))
        if name == "领导姓名" and evidence == "职务":
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        link = cells[0].select_one("a[href]")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
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
