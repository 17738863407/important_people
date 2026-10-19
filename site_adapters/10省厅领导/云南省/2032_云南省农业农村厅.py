from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2032',
 'domain': 'nync.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'yunnan_agriculture_leader_intro_pairs_v1',
 'leader_region_selector': '领导简介',
 'name_selector': '',
 'duty_selector': '',
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
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.yn_zwxxgk_bd:nth-of-type(2) > '
                                               'div.zwxxgk_box:nth-of-type(2) > '
                                               'div.scroll_main.zfxxgk_zfld:nth-of-type(3)',
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


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _html_to_lines(html: str) -> list[str]:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "\n", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", "", html)
    return [line for line in (_clean_text(item) for item in text.splitlines()) if line]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析领导简介区块中的姓名和职务。"""
    from crawler_core.models import PersonRecord

    lines = _html_to_lines(html)
    try:
        start = lines.index("领导简介") + 1
        end = lines.index("职能配置", start)
    except ValueError:
        return []

    records: list[object] = []
    region = lines[start:end]
    index = 0
    while index < len(region) - 1:
        name = re.sub(r"\s+", "", region[index])
        duty = _clean_text(region[index + 1])
        duty = re.sub(r"[（(]\s*挂职\s*[)）]", "", duty).strip(" 、，")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) and "云南" in duty:
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
                )
            )
            index += 2
            continue
        index += 1
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
