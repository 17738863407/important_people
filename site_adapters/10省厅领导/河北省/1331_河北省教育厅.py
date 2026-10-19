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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.hebei.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_hebei_education_leader_text_rows_v1",
        "leader_region_selector": ".art-list2 > div:nth-of-type(2) > div",
        "name_selector": "row text prefix",
        "duty_selector": "row text suffix",
        "detail_link_selector": "",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": None,
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
            "candidate_links": [],
        },
        "risk_flag": "live_text_rows_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".art-list2 > div:nth-of-type(2) > div",
                "name_selector": "row text prefix",
                "duty_selector": "row text suffix",
                "detail_link_selector": "",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网当前 HTML 直接列出委厅领导姓名和职务"},
            "migration": {"source": "legacy_page_rule", "behavior_changed": True},
        },
    }


def extract_row(line: str) -> tuple[str, str] | None:
    text = normalize_space(line)
    match = re.match(r"^(.{2,8}?)\s+(省委|省教育厅|省纪委).+$", text)
    if not match:
        return None
    name = clean_name(match.group(1))
    duty = normalize_space(text[len(match.group(1)) :])
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in soup.select(".art-list2 > div:nth-of-type(2) > div"):
        result = extract_row(node.get_text(" ", strip=True))
        if not result:
            continue
        name, duty = result
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.art-list2 rows；field=姓名+职务文本行",
            }
        )

    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1331"
    main(rule_id_value)
