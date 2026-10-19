from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\u2003", " ").split())


def clean_name(value: str) -> str:
    """规范姓名中的异常空格。"""
    return clean_text(value).replace(" ", "")


def extract_duty(profile: str) -> str:
    """从简介第一句中截取履历性别信息之前的任职表述。"""
    import re

    text = clean_text(profile)
    text = re.split(r"。(?=[男女]，)", text, maxsplit=1)[0]
    if re.match(r"^[男女]，", text):
        return ""
    return text.rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析国家林业和草原局领导专区详情模块。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".kyy_textR.scy_ldzcxl"):
        name = clean_name(card.select_one("#ld_name").get_text(" ", strip=True) if card.select_one("#ld_name") else "")
        profile = clean_text(card.select_one("#ld_bgtitle").get_text(" ", strip=True) if card.select_one("#ld_bgtitle") else "")
        duty = extract_duty(profile)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_forestry_leader_profile_modules_v1",
            }
        )

    return rows


PAGE_RULE = {'rule_id': '0571',
 'domain': 'www.forestry.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_forestry_leader_profile_modules_v1',
 'leader_region_selector': '.kyy_textR.scy_ldzcxl',
 'name_selector': '#ld_name',
 'duty_selector': '#ld_bgtitle第一句',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '领导专区', 'end_anchor': '快速入口', 'include_selectors': ['.kyy_textR.scy_ldzcxl'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '谭光明模块仅有个人基本信息，页面未给出明确职务，默认跳过以避免误抽履历',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.kyy_textR.scy_ldzcxl',
                     'name_selector': '#ld_name',
                     'duty_selector': '#ld_bgtitle第一句',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '领导专区',
                                       'end_anchor': '快速入口',
                                       'include_selectors': ['.kyy_textR.scy_ldzcxl'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'online_static_html_builder',
                           'verified_status': 'online_pending',
                           'behavior_changed': True}}}


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
