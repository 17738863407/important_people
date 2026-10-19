from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4292", "page_type": "市委常委照片卡片", "structure_group": "永州新闻网市委常委列表", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_yongzhou_party_leaders_v1", "leader_region_selector": "市委常委列表 .list-item", "name_selector": "市委常委列表 .list-item label", "duty_selector": "市委常委列表 .list-item span", "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "人物卡片未配置可验证个人详情链接，不能把空报道专辑链接写为详情页。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从当前市委常委卡片直接提取姓名和职务。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".list-item"):
        name_node, duty_node = card.select_one("label"), card.select_one("span")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and "市委" in duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "市委常委当前人物卡片"})
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
