from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2831',
 'domain': 'tyjrt.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_qinghai_veterans_trs_paragraph_sequence_v1',
 'leader_region_selector': '.con-rt.gkzn .zncont .view p',
 'name_selector': 'p strong',
 'duty_selector': 'p',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.con-rt.gkzn .zncont .view p',
                     'name_selector': 'p strong',
                     'duty_selector': 'p',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def _strip_label(value: str, label: str) -> str:
    text = _clean_text(value)
    return _clean_text(text[len(label) :]) if text.startswith(label) else text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析青海省退役军人事务厅领导介绍段落序列。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".con-rt.gkzn .zncont .view p")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    index = 0
    while index < len(paragraphs):
        paragraph = paragraphs[index]
        strong = paragraph.select_one("strong")
        name = _clean_text(strong.get_text(" ", strip=True) if strong else "")
        if not name:
            index += 1
            continue
        duty = ""
        division = ""
        lookahead = index + 1
        while lookahead < len(paragraphs):
            text = _clean_text(paragraphs[lookahead].get_text(" ", strip=True))
            if paragraphs[lookahead].select_one("strong"):
                break
            if text.startswith("职务："):
                duty = _strip_label(text, "职务：")
            elif text.startswith("分工："):
                division = text
            if duty and division:
                break
            lookahead += 1
        if duty:
            key = (name, duty)
            if key not in seen:
                seen.add(key)
                records.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": "",
                        "evidence": duty,
                        "parser": page_rule.get("parser", ""),
                        "selector_summary": "strategy=css；leader=.con-rt.gkzn .zncont .view p；name=p strong；duty=following p startswith 职务；detail=；api_enabled=False",
                    }
                )
        index = max(index + 1, lookahead)
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
