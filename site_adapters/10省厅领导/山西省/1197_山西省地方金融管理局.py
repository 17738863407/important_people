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

PAGE_RULE = {'rule_id': '1197',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_shanxi_finance_profile_paragraphs_v2',
 'leader_region_selector': '.trs_editor_view',
 'name_selector': 'strong',
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
                     'max_detail_links': 0},
 'risk_flag': '正文使用多个段落和行内元素拆分姓名、简历及现任职务，需按姓名边界重组',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.trs_editor_view',
                     'name_selector': 'strong',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'current_online_page',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    text = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s*([，、；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析山西省地方金融管理局领导介绍正文。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；scope=.trs_editor_view；name=strong；duty_pattern=任...。；dedupe=name"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    content = soup.select_one(".trs_editor_view")
    if content is None:
        return rows

    names = []
    for strong in content.select("strong"):
        name = normalize_space(strong.get_text(" ", strip=True)).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and name not in names:
            names.append(name)

    full_text = normalize_space(content.get_text(" ", strip=True))
    for index, name in enumerate(names):
        start = full_text.find(name)
        if start < 0:
            continue
        end = full_text.find(names[index + 1], start + len(name)) if index + 1 < len(names) else len(full_text)
        block = full_text[start:end if end >= 0 else len(full_text)]
        match = re.search(r"任\s*(.+?)[。；;]", block)
        if not match or name in seen:
            continue
        duty = normalize_space(match.group(1).strip("，,。 "))
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
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
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
