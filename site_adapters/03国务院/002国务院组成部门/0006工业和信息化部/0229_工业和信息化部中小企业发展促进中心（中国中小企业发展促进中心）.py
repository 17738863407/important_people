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
    "rule_id": "0229",
    "page_type": "人物列表完整页",
    "structure_group": "中心领导卡片姓名与末段职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ChinaSmeLeaderCardParser_v2",
    "leader_region_selector": "div.newsMsg li",
    "name_selector": "h5",
    "duty_selector": "p:last-of-type",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片前两段为机构名，末段为原始职务；页面无独立人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导卡片DOM顺序抽取姓名和末段原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.newsMsg li")
    if not cards:
        raise RuntimeError("未找到领导卡片 div.newsMsg li")

    rows: list[dict] = []
    for card in cards:
        name_node = card.select_one("h5")
        duty_nodes = card.select("p")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_nodes[-1].get_text(" ", strip=True)) if duty_nodes else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "div.newsMsg li；h5；p:last-of-type",
            }
        )

    if not rows:
        raise RuntimeError("领导卡片未解析到姓名职务记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
