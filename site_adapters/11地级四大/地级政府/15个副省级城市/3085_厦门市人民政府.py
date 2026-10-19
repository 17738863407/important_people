from __future__ import annotations

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
    "rule_id": "3085",
    "page_type": "人物列表完整页",
    "structure_group": "分组职务与组内人物链接",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "XiamenGovernmentLeaderGroupParser_v2",
    "leader_region_selector": "li.szf .nav_l_2021 p",
    "name_selector": "span a[href]",
    "duty_selector": "b",
    "detail_link_selector": "span a[href]",
    "risk_flag": "同一职务节点对应组内多名人物，须按分组DOM顺序展开",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(text: str) -> str:
    """仅清理网页排版空白，不改变原始语义。"""
    return "".join((text or "").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按页面分组顺序展开职务节点下的人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for group in soup.select(rule["leader_region_selector"]):
        duty_node = group.select_one(rule["duty_selector"])
        evidence = _compact_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not evidence:
            continue
        for link in group.select(rule["name_selector"]):
            name = _compact_text(link.get_text(" ", strip=True))
            href = (link.get("href") or "").strip()
            if not name:
                continue
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": "li.szf .nav_l_2021 p > b + span a[href]",
                }
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
