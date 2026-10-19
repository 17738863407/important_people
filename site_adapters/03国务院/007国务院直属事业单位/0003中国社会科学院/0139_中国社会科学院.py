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

PAGE_RULE = {'rule_id': '0139',
 'domain': 'www.cass.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_cass_leaders_v1',
 'leader_region_selector': 'div.ld_jjBox.ldListTop div.ld_jjImg, div.ldListUl5.ldListTop div.ld_jjImg',
 'name_selector': 'div.ld_jjImg p',
 'duty_selector': 'div.ld_jjImg span',
 'detail_link_selector': 'div.ld_jjImg a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'div.ld_jjImg a[href]',
                     'detail_parser': '',
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
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.innerCenter:nth-of-type(3) > '
                                               'div.ld_jjBox.ldListTop:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
            'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
            'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}

PAGE_RULE['locator_strategy'] = 'page_inline_card'
PAGE_RULE['locator']['css'] = {
    'leader_region_selector': PAGE_RULE['leader_region_selector'],
    'name_selector': PAGE_RULE['name_selector'],
    'duty_selector': PAGE_RULE['duty_selector'],
    'detail_link_selector': PAGE_RULE['detail_link_selector'],
    'content_scope': PAGE_RULE['content_scope'],
}
PAGE_RULE['locator']['api'] = {'enabled': False, 'reason': '在线页面包含完整领导卡片，无需接口或详情页'}
PAGE_RULE['locator']['migration'] = {
    'source': 'online_html_review',
    'verified_status': 'online_pending',
    'behavior_changed': True,
}


def clean_text(text: str) -> str:
    """压缩网页中的普通空白与全角空白。"""
    return " ".join((text or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for card in soup.select(page_rule["leader_region_selector"]):
        link = card.select_one("a[href]")
        name_node = card.select_one("p")
        duty_node = card.select_one("span")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        detail_url = urljoin(final_url, link.get("href", "")) if link and final_url else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "source_text": f"{name} {duty}",
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；leader=div.ld_jjImg；"
                    "name=p；duty=span；detail=a[href]；api_enabled=False"
                ),
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
