from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3381',
 'domain': 'zjt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_visible_cards_hubei_housing_department_leader_v1',
 'leader_region_selector': '.leader .list-p li a[href]',
 'name_selector': '.leader h4 b',
 'duty_selector': '.leader h4 b后文本',
 'detail_link_selector': '.leader .list-p li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader .list-p li a[href]',
                     'name_selector': '.leader h4 b',
                     'duty_selector': '.leader h4 b后文本',
                     'detail_link_selector': '.leader .list-p li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用原 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖北省住房和城乡建设厅领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leader .list-p li a[href]"):
        title = link.select_one("h4")
        name_node = title.select_one("b") if title else None
        if not title or not name_node:
            continue
        name = re.sub(r"[\s\u00a0\u3000]+", "", name_node.get_text("", strip=True))
        name_node.extract()
        duty = re.sub(r"[\s\u00a0\u3000]+", "", title.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty:
            continue
        if name in seen:
            continue
        seen.add(name)
        href = str(link.get("href", "")).strip()
        detail_url = urljoin(base_url, href) if href else ""
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or urlparse(detail_url).netloc.lower() != urlparse(base_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(base_url)[0].rstrip('/')
            or not urlparse(detail_url).path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".leader可见卡片b姓名+h4职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()
