from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2739",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_stats_leaders_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_sichuan_stats_leaders_list_v1",
    "leader_region_selector": "dl.leaders-list",
    "name_selector": "dd.leader span:first-of-type",
    "duty_selector": "dd.leader span:nth-of-type(2)",
    "detail_link_selector": "dd.leader a[href]",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "机构设置",
        "include_selectors": ["dl.leaders-list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "dd.leader a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "机关简介页同时包含职责、机构设置和直属单位；严格限定leaders-list",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "dl.leaders-list",
            "name_selector": "dd.leader span:first-of-type",
            "duty_selector": "dd.leader span:nth-of-type(2)",
            "detail_link_selector": "dd.leader a[href]",
            "content_scope": {
                "start_anchor": "领导简介",
                "end_anchor": "机构设置",
                "include_selectors": ["dl.leaders-list"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML的领导简介列表直接包含姓名、职务和详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理页面排版空白，不改变职务语义。"""
    return " ".join((value or "").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导简介列表，继承dd在页面中的原始顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("dl.leaders-list dd.leader"):
        spans = item.select("p > span")
        if len(spans) < 2:
            continue
        name = re.sub(r"\s+", "", spans[0].get_text(" ", strip=True))
        duty = _clean_text(spans[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = ""
        link = item.select_one("a[href]")
        if link:
            candidate = urljoin(final_url or source_url, str(link.get("href") or "").strip())
            parsed = urlparse(candidate)
            real_person_page = bool(re.fullmatch(r"/scstjj/[^/]+/ldxq\.shtml", parsed.path))
            if parsed.netloc.lower() == source_host and real_person_page:
                detail_url = candidate

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_sichuan_stats_leaders_list_v1",
                "selector_summary": "dl.leaders-list dd.leader；前两项span为姓名和职务",
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
