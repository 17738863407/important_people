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
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    text = " ".join(str(value or "").replace("\u3000", " ").split())
    return text.replace("、 ", "、").replace(" ，", "，").replace(" 。", "。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析四川省退役军人事务厅领导介绍人物块。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for box in soup.select(".the-content-box .persons .person-box"):
        name_node = box.select_one(".name > div")
        info_node = box.select_one(".info")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        info = clean_text(info_node.get_text(" ", strip=True) if info_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not info:
            continue
        duty = clean_text(re.split(r"主管工作[:：]", info, maxsplit=1)[0])
        duty = duty.rstrip("。")
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_sichuan_dva_person_boxes_v1",
                "order": str(len(rows) + 1),
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0494',
 'domain': 'dva.sc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_sichuan_dva_person_boxes_v1',
 'leader_region_selector': '.the-content-box .persons .person-box',
 'name_selector': '.the-content-box .persons .person-box .name > div',
 'duty_selector': '.the-content-box .persons .person-box .info',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': '.the-content-box .persons .person-box',
                     'name_selector': '.the-content-box .persons .person-box .name > div',
                     'duty_selector': '.the-content-box .persons .person-box .info before 主管工作',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


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
