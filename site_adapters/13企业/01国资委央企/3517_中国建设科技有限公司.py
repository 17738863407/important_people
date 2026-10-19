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
    """仅从“集团领导”中的“董事会”分组按网页顺序抽取姓名和原始职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    selector = (
        ".content .slider-box > .slider-content[data-content-number='2'] "
        ".slider-box1 > .slider-content[data-content-number='3'] .leader-item"
    )
    for card in soup.select(selector):
        name_node = card.select_one(":scope > h6")
        duty_node = card.select_one(":scope > p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        raw_lines = [line.strip() for line in duty_node.get_text("\n", strip=True).splitlines()]
        lines = [line for line in raw_lines if line]
        duty = lines[1] if len(lines) >= 2 else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_cctc_group_board_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '3517',
 'page_type': '职务分组名单页',
 'structure_group': 'cctc_group_board',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'requests',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_cctc_group_board_v1',
 'leader_region_selector': ".content .slider-box > .slider-content[data-content-number='2'] .slider-box1 > .slider-content[data-content-number='3'] .leader-item",
 'name_selector': ':scope > h6',
 'duty_selector': ':scope > p',
 'detail_link_selector': '',
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': None},
 'risk_flag': '同页同时存在公司领导、集团领导董事会和集团领导高管团队，仅采集集团领导下的董事会',
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
