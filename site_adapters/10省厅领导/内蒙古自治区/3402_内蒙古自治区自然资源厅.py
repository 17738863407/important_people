from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3402',
 'domain': 'zrzy.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_leader_box_inner_mongolia_natural_resources_leader_v1',
 'leader_region_selector': '.leader_box a[href*="/ldjj/"]',
 'name_selector': '领导链接文本',
 'duty_selector': '领导链接文本姓名前后职务',
 'detail_link_selector': '.leader_box a[href*="/ldjj/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader_box a[href*="/ldjj/"]',
                     'name_selector': '领导链接文本',
                     'duty_selector': '领导链接文本姓名前后职务',
                     'detail_link_selector': '.leader_box a[href*="/ldjj/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _split_name_duty(text: str) -> tuple[str, str]:
    text = re.sub(r"[\s\u00a0\u3000]+", " ", text).strip().rstrip("，,；;。")
    colon_match = re.match(r"^(.+?)[:：]\s*([\u4e00-\u9fa5]{2,4})$", text)
    if colon_match:
        return colon_match.group(2), re.sub(r"\s+", "", colon_match.group(1))
    match = re.match(r"^([\u4e00-\u9fa5]{2,4})\s+(.+)$", text)
    if not match:
        return "", ""
    return match.group(1), re.sub(r"\s+", "", match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析内蒙古自治区自然资源厅领导链接卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('.leader_box a[href*="/ldjj/"]'):
        text = re.sub(r"[\s\u00a0\u3000]+", " ", link.get_text(" ", strip=True)).strip()
        name, duty = _split_name_duty(text)
        if not name or not duty or name in seen:
            continue
        if not re.search(r"(党组|厅长|纪检监察组|总督察|监察官)", duty):
            continue
        seen.add(name)
        detail_url = urljoin(base_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(str(page_rule.get("url", "")) or final_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or "/ldjj/" not in detail.path
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
                "selector_summary": ".leader_box领导链接",
            }
        )
    return rows


if __name__ == "__main__":
    main()
