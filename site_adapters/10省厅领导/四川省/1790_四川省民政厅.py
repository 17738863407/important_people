from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1790',
 'domain': 'mzt.sc.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'sichuan_mzt_leader_merged_profile_v1',
 'leader_region_selector': '.list_lingdaoxinxi > li',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': '',
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


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析四川省民政厅领导信息合并页。"""
    from bs4 import BeautifulSoup
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    for item in soup.select(".list_lingdaoxinxi > li"):
        profile = ""
        for line in item.select(".list_lingdaoxinxi_rightBoxLine"):
            title_node = line.select_one(".list_lingdaoxinxi_rightBox_title")
            content_node = line.select_one(".list_lingdaoxinxi_rightBox_content")
            if title_node and content_node and _clean_text(title_node.get_text(" ", strip=True)) == "简历":
                profile = _clean_text(content_node.get_text(" ", strip=True))
                break
        match = re.search(r"(?P<name>[\u4e00-\u9fff]{2,4})，.*?现任(?P<duty>.+?)[。；;]", profile)
        if not match:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="section=.list_lingdaoxinxi; item=li; profile=title 简历; regex=现任",
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
