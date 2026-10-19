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
    "rule_id": "1257",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_transport_leader_attributes",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_transport_leader_attributes_v1",
    "leader_region_selector": ".ldxx-z",
    "name_selector": "a[data-zhiwu][title]",
    "duty_selector": "a[data-zhiwu]的data-zhiwu属性",
    "detail_link_selector": "a[data-zhiwu][href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".ldxx-z"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "attribute_links",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".ldxx-z a[data-zhiwu][href]",
        "detail_name_selector": "title",
        "detail_duty_selector": "data-zhiwu",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "规则入口兼作首位领导详情页，首人详情同址须留空；仅解析.ldxx-z中同时具备title、data-zhiwu和href的领导链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldxx-z",
            "name_selector": "a[data-zhiwu][title]",
            "duty_selector": "a[data-zhiwu]的data-zhiwu属性",
            "detail_link_selector": "a[data-zhiwu][href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": [".ldxx-z"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导目录通过稳定title、data-zhiwu和href属性提供完整数据",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导目录DOM顺序读取姓名、职务属性和独立链接。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_url = str(page_rule.get("url", final_url))
    base_url = final_url or entry_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ldxx-z a[data-zhiwu][href]"):
        name = re.sub(r"\s+", "", _clean_text(str(link.get("title") or link.get_text(" ", strip=True))))
        duty = _clean_text(str(link.get("data-zhiwu", ""))).strip("：:，。")
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip("：:，。")
        candidate_url = urljoin(base_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = "" if candidate_url.rstrip("/") == entry_url.rstrip("/") else candidate_url
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_transport_leader_attributes_v1",
                "selector_summary": ".ldxx-z a；title姓名、data-zhiwu职务、href详情",
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
