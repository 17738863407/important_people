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
    """从领导团队页面的连续人物卡片中按网页顺序抽取姓名和原始职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".nymain > .nywp:not(.nysubnav3) .renlist > li"):
        name_node = card.select_one(":scope > h4")
        duty_node = card.select_one(":scope > p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_dongfang_leadership_cards_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '3495',
 'page_type': '职务分组名单页',
 'structure_group': 'dongfang_leadership_cards',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'requests',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_dongfang_leadership_cards_v1',
 'leader_region_selector': '.nymain > .nywp:not(.nysubnav3) .renlist > li',
 'name_selector': ':scope > h4',
 'duty_selector': ':scope > p',
 'detail_link_selector': '',
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': None},
 'risk_flag': '',
 'confidence': 'high'}

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
