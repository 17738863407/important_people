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


def compact_name(value: str) -> str:
    """去除页面为姓名排版加入的各类空白。"""
    return re.sub(
        r"[\s\u00a0\u2000-\u200f\u3000]+",
        "",
        str(value or ""),
    ).strip()


def clean_text(value: str) -> str:
    """压缩职务组文本中的连续空白。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按人物首次出现顺序聚合现任领导目录中的职务组。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    people: dict[str, list[str]] = {}
    detail_urls: dict[str, str] = {}

    for item in soup.select(".leader_box .leader_item"):
        title_node = item.select_one(".leader_title")
        extra_node = item.select_one(".leader_name")
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        extra = clean_text(extra_node.get_text(" ", strip=True) if extra_node else "")
        if not title:
            continue
        duty = "；".join(part for part in (title, extra) if part)

        for link in item.select(".news_title a[href]"):
            name = compact_name(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name):
                continue
            people.setdefault(name, [])
            if duty not in people[name]:
                people[name].append(duty)
            if name not in detail_urls:
                href = str(link.get("href") or "").strip()
                detail_urls[name] = urljoin(base_url, href) if href else ""

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；selector=.leader_box .leader_item；"
        "name=.news_title a[href]；aggregation=按姓名首次出现顺序合并职务组；"
        "detail=首次出现的人物a[href]"
    )
    for name, duties in people.items():
        evidence = "；".join(duties)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_urls.get(name, ""),
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_hit_current_leader_groups_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0967",
    "domain": "www.hit.edu.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "hit_current_leader_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hit_current_leader_groups_v2",
    "detail_strategy": {
        "required": False,
        "mode": "list_dynamic_links",
        "detail_link_selector": ".news_title a[href]",
    },
    "risk_flag": "同一人物分布于多个职务组；仅按目录顺序聚合，不进入详情页抽取曾任履历或职责",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录已按职务组列出姓名及独立人物链接",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
    },
}


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
