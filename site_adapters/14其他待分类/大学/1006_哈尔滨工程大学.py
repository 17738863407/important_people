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
    """去除页面为姓名和职务排版加入的空白。"""
    return re.sub(
        r"[\s\u3000\u00a0\u2002-\u200b]+",
        "",
        str(value or ""),
    ).strip()


def append_duty(duties_by_name: dict[str, list[str]], name: str, duty: str) -> None:
    """按页面出现顺序为同一人物聚合不同职务组。"""
    duties = duties_by_name.setdefault(name, [])
    if duty and duty not in duties:
        duties.append(duty)


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析哈尔滨工程大学现任领导职务分组。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    duties_by_name: dict[str, list[str]] = {}

    for group in soup.select(".xrld.list_zljg .ld.flex"):
        duty_node = group.find("p")
        if duty_node is None:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not duty:
            continue
        for name_node in group.select("p a"):
            name = clean_text(name_node.get_text(" ", strip=True))
            if re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name):
                append_duty(duties_by_name, name, duty)

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；selector=.xrld.list_zljg .ld.flex；"
        "name=p a；aggregation=按姓名首次出现顺序聚合职务组；detail=none"
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
                "parser": "page_grouped_hrbeu_current_leaders_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1006",
    "domain": "www.hrbeu.edu.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "hrbeu_current_leader_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_grouped_hrbeu_current_leaders_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物分布于多个职务组；姓名a标签无href，禁止把入口页或空链接作为详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "当前静态HTML已按职务组列出全部现任领导",
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
