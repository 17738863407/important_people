from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urldefrag, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3414',
 'domain': 'zrzyt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V008_text_name_nextline_duty_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用原 CSS/HTML 定位'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """沿用原注册解析器，将原始职务映射到依据说明并过滤详情链接。"""
    from crawler_core.parser_registry import parse_with_registered_parser

    rows = parse_with_registered_parser(page_rule, html, final_url, None)
    base_url = urldefrag(final_url)[0].rstrip("/")
    for row in rows:
        row.evidence = str(row.duty or "").strip()
        detail_url = str(row.detail_url or "").strip()
        parsed_detail = urlparse(detail_url)
        if (
            not detail_url
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip("/") == base_url
            or not parsed_detail.path.lower().endswith((".shtml", ".html", ".htm"))
        ):
            row.detail_url = ""
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
