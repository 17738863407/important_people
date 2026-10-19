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


def clean_cell(value: str) -> str:
    """压缩表格单元格中的排版空白。"""
    text = re.sub(
        r"\s+",
        " ",
        str(value or "").replace("\u3000", " ").replace("\u00a0", " "),
    ).strip()
    return re.sub(r"([、，；])\s+", r"\1", text)


def clean_name(value: str) -> str:
    """删除姓名单元格为对齐添加的空格。"""
    return clean_cell(value).replace(" ", "")


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """仅解析现任领导表格的姓名、职务两列。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div#wp_content_w6_0 table tr；"
        "name=第一列；duty=第二列；exclude=分管工作与B角；detail=none"
    )

    table_rows = soup.select("div#wp_content_w6_0 table tr")
    for table_row in table_rows[1:]:
        cells = table_row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        name = clean_name(cells[0].get_text(" ", strip=True))
        duty = clean_cell(cells[1].get_text(" ", strip=True))
        if (
            not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name)
            or not duty
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
                "parser": "page_inline_nuaa_current_leader_table_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2002",
    "domain": "www.nuaa.edu.cn",
    "page_type": "人物表格页",
    "structure_group": "nuaa_current_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nuaa_current_leader_table_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "表格后两列为分管工作和B角，禁止把职责或B角重复姓名当作主职务或新增人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "静态HTML现任领导表格前两列直接包含姓名和职务",
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
