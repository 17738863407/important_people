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
    "rule_id": "4260",
    "page_type": "学院领导卡片链接",
    "structure_group": "上海民航职业技术学院领导卡片列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_shcac_leaders_v1",
    "leader_region_selector": ".leader_wrap",
    "name_selector": "a[href*='/info/1011/'] h3",
    "duty_selector": "a[href*='/info/1011/'] .txt",
    "detail_link_selector": "a[href*='/info/1011/']",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "领导区域内有脚本节点，职务文本包含“详情”装饰文字，需在当前卡片内清理。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序解析姓名、职务和独立个人页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".leader_wrap > a[href*='/info/1011/']"):
        name_node = card.select_one("h3")
        duty_node = card.select_one(".txt")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        for marker in duty_node.select("span"):
            marker.decompose()
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, card["href"]),
                "parser": page_rule["parser"],
                "selector_summary": ".leader_wrap领导卡片姓名、职务和详情链接",
            }
        )
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
