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
    "rule_id": "3295",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_housing_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_housing_leader_list_v1",
    "leader_region_selector": ".ldlist-box .news_list3",
    "name_selector": ".ldlist-box .news_list3 a[href] i",
    "duty_selector": ".ldlist-box .news_list3 a[href]中移除i姓名后的文本",
    "detail_link_selector": ".ldlist-box .news_list3 a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".ldlist-box .news_list3"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".ldlist-box .news_list3 a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "姓名与职务同处一个链接；须先移除明确i姓名节点再提取剩余原文，避免姓名混入依据说明",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldlist-box .news_list3",
            "name_selector": "a[href] i",
            "duty_selector": "a[href]移除i后的文本",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "首条领导记录",
                "end_anchor": "末条领导记录",
                "include_selectors": [".ldlist-box .news_list3 a[href]"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物列表直接提供姓名、职务和人物详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"\s+([、，,])", r"\1", text)


def _extract_duty(link: object) -> str:
    copied_link = BeautifulSoup(str(link), "html.parser").select_one("a")
    if copied_link is None:
        return ""
    copied_name = copied_link.select_one("i")
    if copied_name is None:
        return ""
    copied_name.decompose()
    return _clean_text(copied_link.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM顺序提取明确姓名节点、职务文本和动态详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".ldlist-box .news_list3 a[href]"):
        name_node = link.select_one("i")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _extract_duty(link)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_tianjin_housing_leader_list_v1",
                "selector_summary": ".ldlist-box .news_list3链接；i姓名；移除i后的职务文本",
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
