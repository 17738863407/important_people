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
    "rule_id": "3498",
    "page_type": "人物列表完整页",
    "structure_group": "通用技术集团高管团队卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "GtExecutiveCardParser_v2",
    "leader_region_selector": ".ggtd_gywm.ggtd_564 li",
    "name_selector": ".right-content h2",
    "duty_selector": ".right-content p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "站点偶发把栏目请求重定向至首页；无卡片时用公共raw_http有限重试",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按高管团队卡片顺序提取姓名及全部非重复职务行。"""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select(".ggtd_gywm.ggtd_564 li"):
        from crawler_core.fetcher import fetch_by_raw_requests

        for attempt_offset in range(1, 4):
            retry_result = fetch_by_raw_requests(
                str(rule["url"]),
                max_retries=1,
                attempt_offset=attempt_offset,
            )
            retry_soup = BeautifulSoup(retry_result.html, "html.parser")
            if retry_soup.select(".ggtd_gywm.ggtd_564 li"):
                soup = retry_soup
                break
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".ggtd_gywm.ggtd_564 li"):
        name_node = card.select_one(".right-content h2")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duties = [
            cleaned
            for node in card.select(".right-content p")
            if node.find("p") is None
            if (cleaned := _clean_text(node.get_text(" ", strip=True)))
        ]
        evidence = "；".join(dict.fromkeys(duties))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": (
                    ".ggtd_gywm.ggtd_564 li；.right-content h2姓名；叶级p职务"
                ),
            }
        )
    if not records:
        raise RuntimeError("通用技术集团栏目连续返回首页模板，未取得高管团队卡片")
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
