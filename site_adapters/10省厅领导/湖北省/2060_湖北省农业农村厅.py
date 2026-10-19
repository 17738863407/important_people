from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2060',
 'domain': 'nyt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hubei_agriculture_leader_info_v1',
 'leader_region_selector': '',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用原 HTML 区域定位解析'}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return _clean_text(text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析领导信息列表中的姓名和职务。"""
    from crawler_core.models import PersonRecord

    region_match = re.search(
        r'(?is)<ul\b[^>]*class=["\'][^"\']*\blist-p\b[^"\']*["\'][^>]*>(.*?)</ul>',
        html,
    )
    if not region_match:
        return []

    records: list[object] = []
    for item_html in re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", region_match.group(1)):
        link_match = re.search(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>', item_html)
        title_match = re.search(r"(?is)<h4\b[^>]*>(.*?)</h4>", item_html)
        if not link_match or not title_match:
            continue
        title_parts = re.split(r"(?is)<br\s*/?>", title_match.group(1), maxsplit=1)
        name = _html_to_text(title_parts[0])
        duty = _html_to_text(title_parts[1]) if len(title_parts) > 1 else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name):
            continue
        href = html_lib.unescape(link_match.group(1)).strip()
        detail_url = urljoin(final_url, href)
        parsed_detail = urlparse(detail_url)
        if (
            href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


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
