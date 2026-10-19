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
    "rule_id": "4282", "page_type": "领导简历卡片列表", "structure_group": "西藏投资促进局领导介绍卡片", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_xizang_investment_leaders_v1", "leader_region_selector": ".ldlb-main", "name_selector": ".ldlb-main .ldlb-box .name", "duty_selector": ".ldlb-main .ldlb-box .jl-con", "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "卡片职务标签为空，必须仅在同一人物简历块的现任句中取职务。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从逐人简历块的现任句提取当前职务。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".ldlb-main .ldlb-box"):
        name_node, bio_node = card.select_one(".name"), card.select_one(".jl-con")
        if not name_node or not bio_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        bio = re.sub(r"\s+", "", bio_node.get_text(" ", strip=True))
        match = re.search(r"现任(.+?)。", bio)
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and match:
            duty = match.group(1)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "逐人简历块现任句"})
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
