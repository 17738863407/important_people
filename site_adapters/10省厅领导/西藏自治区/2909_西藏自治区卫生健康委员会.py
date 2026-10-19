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
    "rule_id": "2909",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_health_sidebar_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xizang_health_sidebar_leaders_v1",
    "leader_region_selector": "div.c_l_c_concern",
    "name_selector": "div.c_l_c_concern a[href] .l_c_option_left",
    "duty_selector": "div.c_l_c_concern a[href] .l_c_option_right",
    "detail_link_selector": "div.c_l_c_concern a[href]",
    "content_scope": {
        "start_anchor": "左侧首条领导记录",
        "end_anchor": "左侧末条领导记录",
        "include_selectors": ["div.c_l_c_concern a[href]"],
        "exclude_selectors": ["正文当前详情人物"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.c_l_c_concern a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "入口本身是一名历史详情页，但左侧栏在线直出当前完整领导列表；只解析左侧栏，禁止把正文当前详情人物额外加入",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.c_l_c_concern",
            "name_selector": "a[href] .l_c_option_left",
            "duty_selector": "a[href] .l_c_option_right",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "左侧栏首项",
                "end_anchor": "左侧栏末项",
                "include_selectors": ["div.c_l_c_concern a[href]"],
                "exclude_selectors": ["右侧详情正文"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前HTTP响应已静态直出左侧领导姓名、职务和详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧领导栏DOM顺序提取明确姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.c_l_c_concern a[href]"):
        name_node = link.select_one(".l_c_option_left")
        duty_node = link.select_one(".l_c_option_right")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_xizang_health_sidebar_leaders_v1",
                "selector_summary": "div.c_l_c_concern左侧栏；left姓名；right职务",
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
