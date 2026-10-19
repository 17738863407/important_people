from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '3298',
 'domain': 'zfcxjst.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'hebei_housing_construction_leader_list_v2',
 'leader_region_selector': '.gk-content .wjList #lbUR li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a.titleBT[href]',
 'content_scope': {'start_anchor': '标题',
                   'end_anchor': '',
                   'include_selectors': ['.gk-content .wjList #lbUR'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '普通HTTP返回412，需online浏览器兜底；现行页面不含领导内容iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.gk-content .wjList #lbUR li',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a.titleBT[href]',
                     'content_scope': {'start_anchor': '标题',
                                       'end_anchor': '',
                                       'include_selectors': ['.gk-content .wjList #lbUR'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染后的领导分工列表直接列职务和姓名'},
             'migration': {'source': 'last_batch_online_template',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """河北省住房和城乡建设厅领导分工列表直接列职务和姓名。"""
    parser = str(page_rule["parser"])
    selector_summary = ".gk-content .wjList #lbUR li中的a.titleBT：职务+姓名"
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".gk-content .wjList #lbUR li"):
        link = item.select_one("a.titleBT[href]")
        if link is None:
            continue
        text = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
        match = re.match(r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,5})$", text)
        if not match:
            continue
        name, duty = match.group("name"), match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "parser": parser,
                "selector_summary": selector_summary,
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
