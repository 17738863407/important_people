from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '1286',
 'domain': 'jxt.xizang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_tibet_eit_leader_list_v1',
 'leader_region_selector': 'ul.leader_list li',
 'name_selector': '.leader_desc h1',
 'duty_selector': '.leader_desc p.title',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则字段选择器为空且详情上限过高，页面包含导航栏和侧栏，容易回退到整页弱抽取；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.leader_list li',
                     'name_selector': '.leader_desc h1',
                     'duty_selector': '.leader_desc p.title',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    duty = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", duty)
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty.strip(" ，。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析西藏自治区经济和信息化厅领导成员列表。"""
    soup = BeautifulSoup(html, "html.parser")
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=ul.leader_list li；field=.leader_desc h1 + p.title"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("ul.leader_list li"):
        name_node = item.select_one(".leader_desc h1")
        duty_node = item.select_one(".leader_desc p.title")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": parser,
                "selector_summary": selector_summary,
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    current_file = Path(__file__).resolve()
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
