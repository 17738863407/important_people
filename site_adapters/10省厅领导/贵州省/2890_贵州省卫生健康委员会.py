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
    """压缩网页字段中的排版空白。"""
    text = " ".join(str(value or "").replace("\u3000", " ").split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧领导导航顺序提取h1姓名、p职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = ".PageNavigation.LdzcNav .PageNavCon li a:has(h1):has(p)"

    for source_order, link in enumerate(soup.select(selector), start=1):
        name_node = link.select_one("h1")
        duty_node = link.select_one("p")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = re.sub(r"[（(]挂职[）)]", "", duty).rstrip("，、；; ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_health_left_nav_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2890",
    "page_type": "人物列表完整页",
    "structure_group": "贵州卫健委左侧领导h1-p导航",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_guizhou_health_left_nav_v2",
    "leader_region_selector": ".PageNavigation.LdzcNav .PageNavCon",
    "name_selector": ".PageNavigation.LdzcNav .PageNavCon li a h1",
    "duty_selector": ".PageNavigation.LdzcNav .PageNavCon li a p",
    "detail_link_selector": ".PageNavigation.LdzcNav .PageNavCon li a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "navigation_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "正文与新闻可能包含其他人物，完整范围严格限定左侧领导导航h1-p卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
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
