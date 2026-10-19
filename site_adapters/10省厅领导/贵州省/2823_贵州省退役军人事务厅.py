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
    "rule_id": "2823",
    "domain": "tyjrswt.guizhou.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "guizhou_veterans_leader_directory_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "V011_directory_link_v1",
    "leader_region_selector": "div.ldzc ul.bd_gd",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "li > a[href]",
        "detail_parser": "V001_css_field_pair_v1",
        "detail_name_selector": ".xldr_profile .profile_right .name > p.p1",
        "detail_duty_selector": (
            ".xldr_profile .profile_right .profile "
            ".trs_editor_view > p:first-of-type"
        ),
        "detail_content_selector": "div.ldzc_right",
        "max_detail_links": 20,
    },
    "risk_flag": "入口页目录按顺序链接至独立人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "detail_chain",
}


def _clean_text(text: str) -> str:
    """清理详情字段中的纯排版空白。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析领导目录及详情页，精确删除职务字段开头的固定标签。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("div.ldzc ul.bd_gd li > a[href]"):
        detail_url = requests.compat.urljoin(final_url, str(link.get("href") or ""))
        response = requests.get(
            detail_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        name_node = detail_soup.select_one(".xldr_profile .profile_right .name > p.p1")
        duty_node = detail_soup.select_one(
            ".xldr_profile .profile_right .profile .trs_editor_view > p:first-of-type"
        )
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        raw_duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = re.sub(r"^职\s*务\s*[：:]\s*", "", raw_duty, count=1)
        if not name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "page_guizhou_veterans_detail_v2",
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
