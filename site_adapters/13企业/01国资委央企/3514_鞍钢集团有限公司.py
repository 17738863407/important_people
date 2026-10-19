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
    """从渲染快照的管理团队卡片中抽取姓名和职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".leader-box .leader-item"):
        name_node = card.select_one(".leader-blue")
        duty_node = card.select_one(".leader-text")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
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


PAGE_RULE = {'rule_id': '3514',
 'page_type': '职务分组名单页',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_direct',
 'collector': 'auto',
 'parser': 'page_parse_page',
 'leader_region_selector': '.leader-box .leader-item',
 'name_selector': '.leader-blue',
 'duty_selector': '.leader-text',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': 'requests仅返回Vue空壳；Playwright渲染仍为空壳；现行online最终由Chrome CDP取得9张管理团队卡片',
 'confidence': 'high',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '仅在.leader-box内按DOM顺序提取.leader-blue姓名和同卡.leader-text职务，不扫描页面导航。'}

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
