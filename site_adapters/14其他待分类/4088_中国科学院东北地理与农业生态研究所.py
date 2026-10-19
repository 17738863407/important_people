from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4088",
    "page_type": "领导卡片页",
    "structure_group": "neigae_leader_h5_p_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_neigae_leader_h5_p_card",
    "leader_region_selector": "ul.row",
    "risk_flag": "同一卡片分行展示多项职务，按页面顺序使用全角分号合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐卡片抽取姓名、全部职务行和其唯一人物详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("ul.row > li.col-xs-2"):
        name_node = card.select_one("h5")
        duty_node = card.select_one("p")
        link = card.select_one("a[href]")
        if name_node is None or duty_node is None or link is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duties = [line.strip() for line in duty_node.get_text("\n", strip=True).splitlines() if line.strip()]
        duty = "；".join(duties)
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty,
                         "detail_url": urljoin(final_url, link["href"])})
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
