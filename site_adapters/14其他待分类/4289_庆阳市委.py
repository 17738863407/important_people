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
    "rule_id": "4289", "page_type": "市委领导卡片分组", "structure_group": "庆阳市委领导强结构卡片", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_qingyang_party_leaders_v1", "leader_region_selector": ".leaderHome #swld-swld", "name_selector": ".leaderHome #swld-swld h3.title a", "duty_selector": ".leaderHome #swld-swld h3.title .job", "detail_link_selector": ".leaderHome #swld-swld h3.title a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "页面其余选项卡为人大、政府、政协领导，必须限定市委领导 section。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导卡片 DOM 顺序提取姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".leaderHome #swld-swld li"):
        name_node = card.select_one("h3.title a[href]")
        duty_node = card.select_one("h3.title .job")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, name_node["href"]), "parser": page_rule["parser"], "selector_summary": "市委领导姓名职务卡片"})
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
