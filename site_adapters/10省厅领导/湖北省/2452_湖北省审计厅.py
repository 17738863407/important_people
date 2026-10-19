from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2452',
 'domain': 'sjt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'suppress_detail_url': True,
 'collector': 'static_http',
 'parser': 'page_inline_hubei_audit_list_p_h4_v1',
 'leader_region_selector': '.leader ul.list-p > li > a[href]:has(h4)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.leader ul.list-p > li > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leader ul.list-p > li > a[href]:has(h4)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.leader ul.list-p > li > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面使用原 CSS/HTML 定位解析'}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖北省审计厅领导卡片 h4。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select(".leader ul.list-p > li > a[href]:has(h4)"):
        h4 = item.select_one("h4")
        lines = [_clean_text(line) for line in h4.get_text("\n", strip=True).splitlines()] if h4 else []
        lines = [line for line in lines if line]
        if len(lines) < 2:
            continue
        name = lines[0]
        duty = _clean_text("".join(lines[1:]))
        if not name or not duty:
            continue
        href = str(item.get("href", "")).strip()
        detail_url = urljoin(final_url, href)
        parsed_detail = urlparse(detail_url)
        if (
            href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
            }
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
