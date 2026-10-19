from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从每名领导简介开头抽取集团公司现任职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("div.gywm-news-item"):
        name_node = card.select_one("div.gywm-news-item-title")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        text = re.sub(r"\s+", " ", card.get_text(" ", strip=True)).strip()
        match = re.search(r"(?P<duty>集团公司[^。]{2,100}?)(?:，亦任|。)", text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or match is None:
            continue
        duty = match.group("duty").strip("，, ")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_parse_page",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '3487',
 'page_type': '人物目录详情页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'requests',
 'extract_mode': 'detail_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': 'div.gywm-news-item',
 'name_selector': 'div.gywm-news-item-title',
 'duty_selector': '简介开头“集团公司…”至“亦任”或句号前',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '简介同时含股份公司兼任和历史履历，只保留首个集团公司现任职务短语',
 'confidence': 'high',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '只在集团领导简介卡片内提取首个集团公司现任职务短语；不扫描全页。'}

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
