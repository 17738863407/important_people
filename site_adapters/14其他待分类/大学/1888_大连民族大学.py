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


def clean_text(value: str) -> str:
    """去除表格为中文排版加入的空白。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按当前领导表格行顺序提取职务和姓名。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "leader=main.school-jianjie .table-responsive table.table tbody tr；"
        "duty=td[1]；name=td[2]；detail=none"
    )

    for table_row in soup.select(
        "main.school-jianjie .table-responsive table.table tbody tr"
    ):
        cells = table_row.select("td")
        if len(cells) < 2:
            continue
        duty = clean_text(cells[0].get_text(" ", strip=True))
        name = clean_text(cells[1].get_text(" ", strip=True))
        if (
            not duty
            or not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name)
            or name in seen
        ):
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_dlnu_current_leader_table_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1888",
    "domain": "new.dlnu.edu.cn",
    "page_type": "人物表格页",
    "structure_group": "dlnu_current_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_dlnu_current_leader_table_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面模板含浏览器版本过低提示，online会误判无效；必须解析实时表格，禁止硬编码姓名或使用旧缓存名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "实时原始HTML的现任领导表格直接包含职务和姓名",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
    },
}


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
