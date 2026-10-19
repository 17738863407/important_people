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
    "rule_id": "3063",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_petition_sequential_profiles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_sichuan_petition_sequential_profiles_v1",
    "leader_region_selector": "#cmsArticleContent .szfbgtdiv",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导介绍",
        "end_anchor": "机构职能",
        "include_selectors": ["#cmsArticleContent .szfbgtdiv"],
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
        "max_detail_links": 50,
    },
    "risk_flag": "姓名、简历、职务、分工连续排列；仅配对姓名段与其后职务段，不补机构前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#cmsArticleContent .szfbgtdiv",
            "name_selector": "p",
            "duty_selector": "p",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导介绍",
                "end_anchor": "机构职能",
                "include_selectors": ["#cmsArticleContent .szfbgtdiv"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导介绍分组直接包含按人物顺序排列的姓名和职务段落",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理不换行空格与排版空白，不改变原始职务语义。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名段和后续职务段配对，继承人物在页面中的顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    sections = soup.select("#cmsArticleContent .szfbgtdiv")
    if not sections:
        return []
    container = sections[0]

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_name = ""

    for paragraph in container.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", compact):
            current_name = compact
            continue
        if not current_name or not re.search(r"职\s*务\s*[:：]", text):
            continue

        duty = re.sub(r"^.*?职\s*务\s*[:：]\s*", "", text).rstrip("。 ")
        duty = re.sub(r"[（(]兼[）)]", "", duty).strip("，、； ")
        if duty and current_name not in seen:
            seen.add(current_name)
            rows.append(
                {
                    "name": current_name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": "custom_sichuan_petition_sequential_profiles_v1",
                    "selector_summary": "领导介绍首个szfbgtdiv；姓名段与后续职务段顺序配对",
                }
            )
        current_name = ""

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
