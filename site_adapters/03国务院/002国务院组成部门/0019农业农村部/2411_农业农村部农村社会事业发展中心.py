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
    "rule_id": "2411",
    "domain": "www.shsyzx.agri.cn",
    "page_type": "人物列表完整页",
    "structure_group": "shsyzx_nested_trs_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "chrome_cdp",
    "parser": "page_inline_shsyzx_current_leader_text_v1",
    "leader_region_selector": ".organ_right .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".organ_right .TRS_Editor p"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "chrome_cdp",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "普通HTTP返回403防护页；正文TRS_Editor存在嵌套结构，需选择单一范围并按姓名去重",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".organ_right .TRS_Editor",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".organ_right .TRS_Editor p"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "经Chrome CDP核验后，渲染正文已明确提供当前领导段落"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_chrome_cdp",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_leader_line(value: str) -> tuple[str, str]:
    """从“职务：姓名”人物段落中提取姓名并保留完整原文依据。"""
    text = clean_text(value)
    match = re.fullmatch(r"(主\s*任|副\s*主任)\s*[：:]\s*([\u4e00-\u9fff·\s]{2,8})", text)
    if not match:
        return "", ""
    duty = re.sub(r"\s+", "", match.group(1))
    name = re.sub(r"\s+", "", match.group(2))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导班子正文段落的原始DOM顺序抽取人物。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    scopes = soup.select(".organ_right .TRS_Editor")
    if not scopes:
        return []
    scope = scopes[0]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.organ_right .TRS_Editor；item=p；format=职务：姓名"

    for paragraph in scope.select("p"):
        name, evidence = parse_leader_line(paragraph.get_text(" ", strip=True))
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
