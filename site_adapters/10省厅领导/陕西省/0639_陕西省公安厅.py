from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析陕西省公安厅机关简介页中的领导信息卡片。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = final_url
    seen: set[str] = set()

    for card in soup.select(".con-rt .news-list .img-boxlf"):
        name_node = card.select_one("p.name")
        duty_node = card.select_one("p.position")
        link = card.select_one("a[href]")
        name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(source_url, str(link.get("href") or "")) if link else "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_shaanxi_police_news_list_cards_v1",
                "order": str(len(rows) + 1),
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0639',
 'domain': 'gat.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shaanxi_police_news_list_cards_v1',
 'leader_region_selector': '.con-rt .news-list .img-boxlf',
 'name_selector': '.con-rt .news-list .img-boxlf p.name',
 'duty_selector': '.con-rt .news-list .img-boxlf p.position',
 'detail_link_selector': '.con-rt .news-list .img-boxlf a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.con-rt .news-list .img-boxlf',
                     'name_selector': '.con-rt .news-list .img-boxlf p.name',
                     'duty_selector': '.con-rt .news-list .img-boxlf p.position',
                     'detail_link_selector': '.con-rt .news-list .img-boxlf a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


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
