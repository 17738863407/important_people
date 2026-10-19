from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {'rule_id': '2054',
 'domain': 'nynct.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_shanxi_agriculture_leader_paragraph_v1',
 'leader_region_selector': 'div.pc-wrapper div.trweb.article-body',
 'name_selector': 'p > strong',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['div.trs_editor_view.TRS_UEDITOR.trs_paper_default.trs_web'],
                   'exclude_selectors': ['div.mobile-wrapper']},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': 'PC与移动端正文重复，仅取PC容器；段落为加粗姓名+职务文本',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.pc-wrapper div.trweb.article-body',
                     'name_selector': 'p > strong',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['div.trs_editor_view.TRS_UEDITOR.trs_paper_default.trs_web'],
                                       'exclude_selectors': ['div.mobile-wrapper']}},
             'api': {'enabled': False,
                     'reason': '领导名单直接位于静态正文段落，姓名加粗、职务为段落其余文本，无需接口'}}}


def clean_text(value: str) -> str:
    """清理排版空白：统一全角/半角空格，保留姓名与职务文本的原始顺序。"""
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ").replace("\u2002", " ")
    text = " ".join(text.split())
    return text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析山西省农业农村厅厅领导正文页。

    PC 端容器 div.pc-wrapper 下的正文区以段落呈现全部厅领导，
    每段为“加粗姓名 + 职务文本”；移动端存在隐藏重复块，必须只取 PC 容器。
    """
    soup = BeautifulSoup(html, "html.parser")
    pc_wrapper = soup.select_one("div.pc-wrapper")
    if pc_wrapper is None:
        return []
    article = pc_wrapper.select_one("div.trweb.article-body")
    if article is None:
        return []
    editor = article.find("div", class_=lambda value: value and "trs_editor_view" in value)
    container = editor if editor is not None else article

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.pc-wrapper div.trweb.article-body "
        "div.trs_editor_view；name=p>strong；duty=p文本-姓名；detail=无"
    )
    for paragraph in container.find_all("p", recursive=False):
        strong = paragraph.find("strong", recursive=False)
        if strong is None:
            continue
        name = clean_text(strong.get_text(" ", strip=True))
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        if not name or not full_text or name in seen_names:
            continue
        seen_names.add(name)
        duty_text = full_text
        if full_text.startswith(name):
            duty_text = full_text[len(name):].strip(" ：:，,。.；;")
        rows.append({
            "name": name,
            "duty": duty_text,
            "detail_url": "",
            "evidence": duty_text,
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
