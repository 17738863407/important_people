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

PAGE_RULE = {'rule_id': '3269',
 'domain': 'www.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_paragraph_yunnan_gov_office_leader_v1',
 'leader_region_selector': '.trs_key4format',
 'name_selector': '.trs_key4format p 句末姓名',
 'duty_selector': '.trs_key4format p 姓名前职务',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > center > div.articlebg',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
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
    """解析云南省人民政府办公厅班子成员段落。"""
    from bs4 import BeautifulSoup

    surnames = "姜雷黄马张陶尹毛赵冯沈李杨王卜荣彭刘陈周吴郑孙郭高林何罗梁宋徐胡朱"

    def split_duty_name(line: str) -> tuple[str, str] | None:
        line = re.sub(r"[\s\u00a0]+", "", line).rstrip("。；;")
        for length in (3, 2):
            if len(line) <= length:
                continue
            name = line[-length:]
            if name[0] in surnames and re.fullmatch(r"[\u4e00-\u9fa5]{2,3}", name):
                duty_part = line[:-length].strip("，、, ")
                if duty_part:
                    return duty_part, name
        return None

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".trs_key4format") or soup
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in region.select("p"):
        text = paragraph.get_text("", strip=True)
        if not text or not re.search(r"(秘书长|主任|党组成员|党组书记)", text):
            continue
        parsed = split_duty_name(text)
        if not parsed:
            continue
        duty_part, name = parsed
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty_part,
                "detail_url": "",
                "evidence": duty_part,
                "parser": page_rule["parser"],
                "selector_summary": ".trs_key4format p 句末姓名",
            }
        )
    return rows


if __name__ == "__main__":
    main()
