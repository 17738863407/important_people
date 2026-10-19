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
    "rule_id": "1680",
    "domain": "www.most.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "most_dept_profile_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_most_dept_profile_table_v1",
    "leader_region_selector": ".dept_profile table",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".dept_profile table"],
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
    "risk_flag": "同一职务单元格可包含多名人物及挂职注记",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".dept_profile table",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".dept_profile table"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "在线响应已直接包含权威人物表格，无需接口或浏览器渲染",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白，不改变原始语义。"""
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格原始行序及单元格内姓名顺序抽取人物。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = "strategy=custom_parse_page；leader=.dept_profile table；row=tr；cells=td"

    for table_row in soup.select(".dept_profile table tr"):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue

        raw_duty = clean_text(cells[0].get_text(" ", strip=True)).rstrip(":：").replace(" ", "")
        names_text = clean_text(cells[1].get_text(" ", strip=True))
        if not raw_duty or "司长" not in raw_duty or not names_text:
            continue

        evidence = f"{raw_duty}：{names_text}"
        for part in re.split(r"[、,，]", names_text):
            person_text = clean_text(part)
            if not person_text:
                continue
            note_match = re.fullmatch(r"(.+?)([（(].+?[）)])", person_text)
            name = clean_text(note_match.group(1) if note_match else person_text).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                continue

            key = (name, evidence)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": "",
                    "detail_url": "",
                    "evidence": raw_duty,
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
