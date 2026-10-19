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
    "rule_id": "0534",
    "domain": "www.fecomee.org.cn",
    "page_type": "人物表格页",
    "structure_group": "fecomee_leader_profile_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "table_rows",
    "collector": "static_http",
    "parser": "page_inline_fecomee_current_leaders_v1",
    "leader_region_selector": ".TRS_Editor table[border='1']",
    "name_selector": "tr td:nth-child(2)逗号前文本",
    "duty_selector": "tr td:first-child",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "党委书记、主任",
        "end_anchor": "",
        "include_selectors": [".TRS_Editor table[border='1']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "站点HTTPS证书主机名不匹配；第二列同时含姓名、职务和简历，依据只取第一列原始职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".TRS_Editor table[border='1']",
            "name_selector": "tr td:nth-child(2)逗号前文本",
            "duty_selector": "tr td:first-child",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "党委书记、主任",
                "end_anchor": "",
                "include_selectors": [".TRS_Editor table[border='1']"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前原始HTML表格已提供完整现任领导姓名、职务和简历"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白及中文标点周边空格。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()
    text = re.sub(r"\s+([，、；：])", r"\1", text)
    return re.sub(r"([，、；：])\s+", r"\1", text)


def parse_name(value: str) -> str:
    """从“姓名，职务，简历”第二列中提取行首姓名。"""
    match = re.match(r"([\u4e00-\u9fff·]{2,5})[，,、]", clean_text(value))
    return match.group(1) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导表格原始行顺序抽取姓名和第一列职务。"""
    del final_url
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(".TRS_Editor table[border='1']")
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.TRS_Editor table[border=1]；name=td[1]逗号前；duty=td[0]"

    for table_row in table.select(":scope > tbody > tr, :scope > tr"):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        evidence = clean_text(cells[0].get_text(" ", strip=True))
        name = parse_name(cells[1].get_text(" ", strip=True))
        if not name or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
    return rows


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
