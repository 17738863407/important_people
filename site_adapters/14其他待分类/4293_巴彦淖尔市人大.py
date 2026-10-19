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
    "rule_id": "4293", "page_type": "人大常委会领导照片卡片", "structure_group": "巴彦淖尔人大常委会领导卡片", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_byne_congress_leaders_v1", "leader_region_selector": ".newsContainer1", "name_selector": ".newsContainer1 a.tcenter[title]", "duty_selector": "卡片末个文本 div", "detail_link_selector": ".newsContainer1 a.tcenter[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "同页导航含常委会、主任会新闻，人物只取常委会领导卡片。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人大常委会领导卡片的页面顺序提取字段。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".newsContainer1 a.tcenter[title][href]"):
        blocks = card.find_all("div", recursive=False)
        if len(blocks) < 2:
            continue
        name = re.sub(r"\s+", "", card.get("title", ""))
        duty = re.sub(r"\s+", "", blocks[-1].get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,6}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, card["href"]), "parser": page_rule["parser"], "selector_summary": "常委会领导照片卡片"})
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
