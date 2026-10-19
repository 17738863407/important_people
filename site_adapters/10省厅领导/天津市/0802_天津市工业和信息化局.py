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
    "rule_id": "0802",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_industry_leader_text_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_industry_leader_text_list_v1",
    "leader_region_selector": "ul.news_list2.news_list3",
    "name_selector": "li文本首段",
    "duty_selector": "li文本姓名后部分",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["ul.news_list2.news_list3"],
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
    "risk_flag": "列表项为姓名与职务连续文本；在明确领导列表边界内按首个排版空格切分，不使用机构名或职务关键词过滤",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.news_list2.news_list3",
            "name_selector": "li文本首段",
            "duty_selector": "li文本姓名后部分",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": ["ul.news_list2.news_list3"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导列表直接包含6组姓名和职务文本",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _split_name_duty(value: str) -> tuple[str, str]:
    """按限定列表项中的首个排版空格切分姓名与职务。"""
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)", _clean_text(value))
    if not match:
        return "", ""
    return match.group("name"), match.group("duty").strip(" ：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM顺序解析姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("ul.news_list2.news_list3 > li"):
        name, duty = _split_name_duty(item.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_industry_leader_text_list_v1",
                "selector_summary": "ul.news_list2.news_list3直属li；首个排版空格分隔姓名与职务",
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
