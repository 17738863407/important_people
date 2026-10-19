from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0653',
 'domain': 'www.gd.gov.cn',
 'page_type': '图片名单型',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '图片承载',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'image_asset',
 'parser': 'page_online_gdgov_leader_image_alt_v1',
 'leader_region_selector': '.con .h5, .con img[alt], .con li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"image_asset","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '领导信息存储在图片中',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.con .h5, .con img[alt], .con li',
                     'name_selector': 'img alt/title 或 p',
                     'duty_selector': '.h5分组标题',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面图片alt/title和分组标题直接包含领导名单'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析省政府领导图片名单的 alt/title 和分组职务。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from bs4.element import Tag

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".con") or soup
    page_url = str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    current_duty = ""
    seen: set[str] = set()

    for node in container.descendants:
        if not isinstance(node, Tag):
            continue
        classes = node.get("class") or []
        if node.name == "div" and "h5" in classes:
            current_duty = re.sub(r"[\s:：]+", "", node.get_text(" ", strip=True))
            continue
        if node.name not in {"img", "li"} or not current_duty:
            continue
        name = ""
        link_node = node.find_parent("a") if node.name == "img" else node.select_one("a[href]")
        if node.name == "img":
            name = str(node.get("alt") or node.get("title") or "")
        else:
            name_node = node.select_one("p") or node.select_one("img[alt]")
            if name_node:
                name = name_node.get_text(" ", strip=True) if name_node.name == "p" else str(name_node.get("alt", ""))
        name = re.sub(r"[\s\u3000\xa0]+", "", name)
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        href = str(link_node.get("href", "")) if link_node else ""
        detail_url = urljoin(final_url or page_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == page_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": current_duty,
                "detail_url": detail_url,
                "evidence": current_duty,
                "parser": parser,
                "selector_summary": ".con .h5分组 + 图片alt/title或卡片p",
            }
        )
        seen.add(name)

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
