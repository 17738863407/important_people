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
    """清理正文中的BOM和排版空白。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\ufeff", "").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态遍历机构领导目录，并读取详情正文第一条职务句。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#tableli01 a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        href = str(link.get("href") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not re.search(r"/html/4343/\d+\.html$", href):
            continue
        detail_url = urljoin(final_url, href)
        try:
            fetched = fetch_html_with_strategy(detail_url, "raw_http")
        except Exception:
            continue
        detail_soup = BeautifulSoup(fetched.html, "html.parser")
        title_text = clean_text(detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
        if name not in title_text:
            continue
        page_text = clean_text(detail_soup.get_text(" ", strip=True))
        match = re.search(r"【字体[：:]\s*大\s*中\s*小\s*】\s*([^。]{2,200}。)", page_text)
        if match is None:
            continue
        evidence = clean_text(match.group(1))
        evidence = evidence.rstrip("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": fetched.final_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_qinghai_wsb_list_detail_v2",
                "selector_summary": "list=#tableli01 a[href=/html/4343/id.html]；detail title姓名回指；duty=字体控件后正文第一句",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2973",
    "page_type": "人物目录详情页",
    "structure_group": "qinghai_wsb_leader_directory",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_qinghai_wsb_list_detail_v2",
    "leader_region_selector": "#tableli01 a[href]",
    "name_selector": "人物详情链接文本",
    "duty_selector": "详情字体控件后正文第一句",
    "detail_link_selector": "#tableli01 a[href*='/html/4343/']",
    "content_scope": {
        "start_anchor": "机构领导",
        "end_anchor": "",
        "include_selectors": ["#tableli01"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "#tableli01 a[href*='/html/4343/']",
        "detail_name_selector": "title",
        "detail_duty_selector": "字体控件后正文第一句",
        "detail_content_selector": "正文字体控件之后",
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
            "leader_region_selector": "#tableli01 a[href]",
            "name_selector": "人物详情链接文本",
            "duty_selector": "详情字体控件后正文第一句",
            "detail_link_selector": "#tableli01 a[href*='/html/4343/']",
            "content_scope": {
                "start_anchor": "机构领导",
                "end_anchor": "",
                "include_selectors": ["#tableli01"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态领导目录与人物详情正文可在线稳定复现"},
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
