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
    """解析安徽省退役军人事务厅领导信息模块。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = final_url or str(page_rule.get("url", ""))

    for box in soup.select(".ls-leader .leader-box"):
        duty_node = box.select_one(".leader-tit")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in box.select("li a[href]"):
            name_node = link.select_one(".img_title, .img-title")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else link.get("title", "")).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            href = str(link.get("href") or "").strip()
            detail_url = ""
            if href and not href.lower().startswith(("#", "javascript:")):
                candidate_url = urljoin(source_url, href)
                if candidate_url.rstrip("/") != source_url.rstrip("/"):
                    detail_url = candidate_url
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_inline_anhui_dva_leader_boxes_v1",
                }
            )
    return rows


PAGE_RULE = {'rule_id': '0491',
 'domain': 'dva.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_anhui_dva_leader_boxes_v1',
 'leader_region_selector': '.ls-leader .leader-box',
 'name_selector': '.ls-leader .leader-box li a .img_title',
 'duty_selector': '.ls-leader .leader-box .leader-tit',
 'detail_link_selector': '.ls-leader .leader-box li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ls-leader .leader-box',
                     'name_selector': '.ls-leader .leader-box li a .img_title',
                     'duty_selector': '.ls-leader .leader-box .leader-tit',
                     'detail_link_selector': '.ls-leader .leader-box li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面按既有领导分组选择器解析'}}}


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
