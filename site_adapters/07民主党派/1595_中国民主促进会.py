from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1595',
 'domain': 'www.mj.org.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'mj_current_leader_cards_v1',
 'leader_region_selector': 'html > body.g-mobile > div.g_bdw > div.g-contentWrap:nth-of-type(5) > '
                           'div.m-wrap.clearfix:nth-of-type(2) > div.m-layers.m-right:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body.g-mobile > div.g_bdw > div.g-contentWrap:nth-of-type(5) > '
                                               'div.m-wrap.clearfix:nth-of-type(2) > '
                                               'div.m-layers.m-right:nth-of-type(3)',
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析民进中央现任主席、副主席卡片。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.select(".x_mjld_xr .m-peo a[href], .x_mjld_xr .m-peo1 a[href]"):
        text = link.get_text(" ", strip=True)
        if not text:
            continue
        duty = ""
        name = text
        if text.endswith("常务副主席"):
            name = text[: -len("常务副主席")]
            duty = "常务副主席"
        elif text.endswith("副主席"):
            name = text[: -len("副主席")]
            duty = "副主席"
        elif text.endswith("主席"):
            name = text[: -len("主席")]
            duty = "主席"
        name = name.strip()
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href") or ""))
        rows.append(
            PersonRecord(
                organization=str(page_rule.get("organization", "")),
                url=str(page_rule.get("url", "")),
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser="mj_current_leader_cards_v1",
                selector_summary="leader=.x_mjld_xr .m-peo/.m-peo1 a; pattern=姓名+主席/副主席",
            )
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
