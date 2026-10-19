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
    "rule_id": "3946",
    "domain": "www.maszx.gov.cn",
    "page_type": "领导名单双列表格",
    "structure_group": "maanshan_cppcc_leader_table_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_maanshan_cppcc_table_v1",
    "leader_region_selector": ".showNr table",
    "name_selector": "td:nth-of-type(2) p",
    "duty_selector": "td:nth-of-type(1) p",
    "content_scope": {"include_selectors": [".showNr table"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一表格行可能并列多项职务和多名人物，须在行内按段落顺序一一对应",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".showNr table",
            "duty_selector": "td:nth-of-type(1) p",
            "name_selector": "td:nth-of-type(2) p",
        },
        "api": {"enabled": False, "reason": "静态正文表格已直接包含当前领导职务和姓名"},
    },
}


def normalize_text(value: str) -> str:
    """删除字段中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def is_person_name(value: str) -> bool:
    """校验包含常用汉字及扩展区汉字的二至四字中文姓名。"""
    return bool(re.fullmatch(r"[\u3400-\u9fff\U00020000-\U0002ebef·]{2,4}", value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐行读取双列表格，并将同一行多段职务与姓名按原序配对。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".showNr table")
    if table is None:
        raise RuntimeError("未找到领导名单表格 .showNr table")
    rows: list[dict[str, str]] = []
    for table_row in table.select("tr"):
        cells = table_row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        duties = [normalize_text(node.get_text(" ", strip=True)) for node in cells[0].select("p")]
        names = [normalize_text(node.get_text(" ", strip=True)) for node in cells[1].select("p")]
        duties = [value for value in duties if value]
        names = [value for value in names if is_person_name(value)]
        if len(duties) != len(names):
            raise RuntimeError(f"表格行职务与姓名数量不一致：{len(duties)} 对 {len(names)}")
        for duty, name in zip(duties, names, strict=True):
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".showNr table行内左列职务段落与右列姓名段落顺序配对",
                }
            )
    if not rows:
        raise RuntimeError("领导名单表格未解析出有效人物")
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
