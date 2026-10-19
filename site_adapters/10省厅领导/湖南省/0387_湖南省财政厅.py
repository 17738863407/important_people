from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0387',
 'domain': 'czt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_hunan_czt_jgld_table_v1',
 'leader_region_selector': 'table tbody tr',
 'name_selector': 'table tbody tr td:first-child a[href]',
 'duty_selector': 'table tbody tr td:nth-child(2)',
 'detail_link_selector': 'table tbody tr td:first-child a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'table tbody tr',
                     'name_selector': 'table tbody tr td:first-child a[href]',
                     'duty_selector': 'table tbody tr td:nth-child(2)',
                     'detail_link_selector': 'table tbody tr td:first-child a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面使用原 CSS/HTML 机构领导表格定位'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖南省财政厅机构领导表格。"""
    import re
    from urllib.parse import urldefrag, urljoin, urlparse

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []

    for row in soup.select("table tbody tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        link = cells[0].select_one("a[href]")
        if link is None:
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", link.get_text(" ", strip=True))
        duty = re.sub(r"[\s\u3000\xa0]+", "", cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        if not re.search(r"党组|厅长|纪检", duty):
            continue
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(final_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
                "selector_summary": "机构领导table tbody tr",
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
