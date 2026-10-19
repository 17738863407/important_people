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


def clean_text(value: str) -> str:
    """压缩动态DOM姓名和职务节点中的排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(value or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析现任领导班子职务组并按姓名首次出现顺序聚合。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("li.wp_sublist.sublist-1")
    if scope is None:
        return []

    duties_by_name: dict[str, list[str]] = {}
    for item in scope.select("ul.news_list li"):
        job_node = item.select_one("span.job")
        duty = clean_text(job_node.get_text(" ", strip=True) if job_node else "")
        if not duty:
            continue
        for name_node in item.select("span.name"):
            name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name):
                continue
            duties_by_name.setdefault(name, [])
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；scope=li.wp_sublist.sublist-1；"
        "group=ul.news_list li；duty=span.job；name=span.name；"
        "aggregation=按姓名首次出现顺序聚合；detail=none"
    )
    for name, duties in duties_by_name.items():
        evidence = "；".join(duties)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_njust_current_leaders_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1949",
    "domain": "www.njust.edu.cn",
    "page_type": "人物表格页",
    "structure_group": "njust_current_leader_groups",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_njust_current_leaders_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "requests与Playwright无法取得有效DOM，在线核验仅Chrome CDP稳定；必须限定sublist-1现任领导班子",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "Chrome渲染DOM中的现任领导班子职务组直接包含姓名和职务",
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
