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

PAGE_RULE = {'rule_id': '0641',
 'domain': 'gat.xizang.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'xizang_police_inline_leader_cards_v1',
 'leader_region_selector': '.zy-gl-rt .ldxx',
 'name_selector': '.zy-gl-rt .ldxx .rt span',
 'duty_selector': '.zy-gl-rt .ldxx .rt p 文本中“现任”后内容',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zy-gl-rt .ldxx',
                     'name_selector': '.zy-gl-rt .ldxx .rt span',
                     'duty_selector': '.zy-gl-rt .ldxx .rt p 文本中“现任”后内容',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.zy-gl-rt .ldxx；"
        "name=.zy-gl-rt .ldxx .rt span；duty=.zy-gl-rt .ldxx .rt p现任后；"
        "detail=none；api_enabled=False"
    )
    for block in soup.select(".zy-gl-rt .ldxx"):
        name_node = block.select_one(".rt span")
        text_node = block.select_one(".rt p")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(text_node.get_text(" ", strip=True) if text_node else block.get_text(" ", strip=True))
        duty_match = re.search(r"现任(?P<duty>.+?)[。；;]", evidence)
        duty = clean_text(duty_match.group("duty")).strip(" ，,。；;") if duty_match else ""
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        })
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
