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
    "rule_id": "4060",
    "domain": "nao.cas.cn",
    "page_type": "人物卡片列表",
    "structure_group": "nao_current_leader_cards_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_nao_current_leader_cards_v1",
    "leader_region_selector": "ul#content.xrld-img",
    "name_selector": ".box-info .box-title.h16",
    "duty_selector": ".box-info .box-title.h14",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "页头下拉菜单含兼任领导名单；正文卡片中的 href 位于 span 而非可点击链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清除姓名和职务节点中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文可见人物卡片顺序提取姓名和卡片职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul#content.xrld-img")
    if region is None:
        raise RuntimeError("未找到现任领导正文区域 ul#content.xrld-img")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in region.select(":scope > li"):
        name_node = item.select_one(".box-info .box-title.h16")
        duty_node = item.select_one(".box-info .box-title.h14")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule["parser"]),
                "selector_summary": "ul#content.xrld-img > li；.h16姓名 + .h14职务",
            }
        )
    if not rows:
        raise RuntimeError("现任领导正文区域未提取到有效人物卡片")
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
