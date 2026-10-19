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

PAGE_RULE = {'rule_id': '3387',
 'domain': 'zjt.shanxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_paragraph_parentheses_shanxi_housing_department_leader_v1',
 'leader_region_selector': '正文领导分工p段落',
 'name_selector': '段落开头姓名',
 'duty_selector': '姓名后括号内职务',
 'detail_link_selector': '',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div',
                     'name_selector': '段落开头姓名',
                     'duty_selector': '姓名后括号内职务',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析山西省住房和城乡建设厅领导分工合并页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.find_all("p"):
        text = re.sub(r"[\u00a0\u3000]+", " ", paragraph.get_text(" ", strip=True))
        text = re.sub(r"\s+", " ", text).strip()
        match = re.match(r"^([\u4e00-\u9fa5](?:\s*[\u4e00-\u9fa5]){1,3})\s*（\s*([^）]{2,80})\s*）$", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = re.sub(r"\s+", "", match.group(2)).rstrip("，,；;")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        if not re.search(r"厅长|纪检监察组|巡视员|总工程师", duty):
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "领导分工p段落姓名括号职务",
                "order": str(len(rows) + 1),
            }
        )
    return rows


if __name__ == "__main__":
    main()
