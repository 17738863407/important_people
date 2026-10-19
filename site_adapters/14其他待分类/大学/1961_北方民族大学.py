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


def clean_text(value: str) -> str:
    """去除职务和姓名节点中的排版空白。"""
    return re.sub(
        r"[\s\u3000\u00a0]+",
        "",
        str(value or ""),
    ).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析桌面端现任领导职务分组并按姓名聚合。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    duties_by_name: dict[str, list[str]] = {}
    detail_urls: dict[str, str] = {}

    for item in soup.select(".adldlist.pc li"):
        duty_node = item.select_one(".adldlist-hd")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in item.select(".adldlist-bd a[href]"):
            name = clean_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name):
                continue
            duties_by_name.setdefault(name, [])
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)
            if name not in detail_urls:
                href = str(link.get("href") or "").strip()
                detail_urls[name] = urljoin(base_url, href) if href else ""

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；scope=.adldlist.pc；group=li；"
        "duty=.adldlist-hd；name=.adldlist-bd a[href]；"
        "aggregation=按姓名首次出现顺序聚合；detail=首次人物a[href]"
    )
    for name, duties in duties_by_name.items():
        evidence = "；".join(duties)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_urls.get(name, ""),
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_nmu_current_leader_groups_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1961",
    "domain": "www.nmu.edu.cn",
    "page_type": "职务分组名单页",
    "structure_group": "nmu_current_leader_groups_desktop",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nmu_current_leader_groups_v2",
    "detail_strategy": {
        "required": False,
        "mode": "list_dynamic_links",
        "detail_link_selector": ".adldlist.pc .adldlist-bd a[href]",
    },
    "risk_flag": "页面同时含桌面和移动端重复领导结构；只解析adldlist.pc并按姓名聚合多个职务组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "静态HTML桌面端职务分组直接包含姓名及独立人物链接",
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
