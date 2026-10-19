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
    "rule_id": "4352",
    "domain": "ecro.mee.gov.cn",
    "page_type": "人物列表页",
    "structure_group": "ecro_role_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_ecro_role_list_v1",
    "leader_region_selector": "div.main_right_m",
    "name_selector": "li a[title]",
    "duty_selector": "title",
    "detail_link_selector": "li a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.main_right_m"],
        "exclude_selectors": ["div.page"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_anchor",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "职务来自当前入口页标题，姓名与详情链接来自右侧人员列表",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.main_right_m",
            "name_selector": "li a[title]",
            "duty_selector": "title",
            "detail_link_selector": "li a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["div.main_right_m"],
                "exclude_selectors": ["div.page"],
            },
        },
        "api": {"enabled": False, "reason": "人员列表及职务标题由静态HTML直接提供"},
        "migration": {
            "source": "manual_online_verification",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析当前职务栏目中的人员列表。"""
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    duty = clean_text(title.split("-", 1)[0])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.main_right_m li a[href][title]"):
        name = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "div.main_right_m li a；职务取当前页面标题",
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
