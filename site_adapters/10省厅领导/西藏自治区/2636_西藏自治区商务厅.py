from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2636',
 'domain': 'swt.xizang.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'xizang_commerce_duty_colon_name_v1',
 'leader_region_selector': '厅领导列表链接文本',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.centerWidth:nth-of-type(3) > '
                                               'div.nxz-overview.nxz-overview-leader:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线厅领导列表直接含职务姓名'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析西藏自治区商务厅“职务：姓名”领导列表。"""
    rows = []
    seen = set()
    page_url = final_url
    pattern = re.compile(r'href="([^"]+)"[^>]*>\s*([\u4e00-\u9fa5、，]+(?:厅长|主任|组长|巡视员))：([\u4e00-\u9fa5]{2,4})\s*<', re.S)
    for detail_path, duty, name in pattern.findall(html):
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(page_url, detail_path),
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "厅领导列表链接文本：职务：姓名",
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
