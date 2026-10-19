from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理网页排版空白。"""
    text = re.sub(r"\s+", " ", value or "").strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录顺序抓取人物详情，并提取可回指的完整“现任”句。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".con-rt.zd ul.ul3 > li > a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            fetched = fetch_html_with_strategy(detail_url, "raw_http")
        except Exception:
            continue
        detail_soup = BeautifulSoup(fetched.html, "html.parser")
        title_text = clean_text(detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
        content = detail_soup.select_one(".view")
        if content is None or name not in title_text:
            continue
        content_text = clean_text(content.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]{2,150}。", content_text)
        if current_match is None:
            continue
        evidence = re.sub(r"^现任\s*", "", clean_text(current_match.group(0))).rstrip("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": fetched.final_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_qinghai_stats_list_detail_v2",
                "selector_summary": "list=.con-rt.zd ul.ul3>li>a；detail title姓名回指；duty=.view完整现任句",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2738",
    "page_type": "人物目录详情页",
    "structure_group": "qinghai_stats_leader_directory",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_qinghai_stats_list_detail_v2",
    "leader_region_selector": ".con-rt.zd ul.ul3 > li > a[href]",
    "name_selector": "目录链接文本",
    "duty_selector": "详情.view完整现任句",
    "detail_link_selector": ".con-rt.zd ul.ul3 > li > a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".con-rt.zd ul.ul3"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "raw_http",
        "detail_link_selector": ".con-rt.zd ul.ul3 > li > a[href]",
        "detail_name_selector": "title",
        "detail_duty_selector": ".view中的完整现任句",
        "detail_content_selector": ".view",
        "max_detail_links": 50,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".con-rt.zd ul.ul3 > li > a[href]",
            "name_selector": "目录链接文本",
            "duty_selector": "详情.view完整现任句",
            "detail_link_selector": ".con-rt.zd ul.ul3 > li > a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": [".con-rt.zd ul.ul3"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态目录和详情正文可在线稳定复现"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
