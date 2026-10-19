from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0794',
 'domain': 'gxt.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shanxi_gxt_content_card_p_title_v1',
 'leader_region_selector': 'div.h-content div.content a[href] p[title]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'div.h-content div.content a[href]',
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
 'risk_flag': '页面导航下拉包含重复厅领导名单，需限定主内容div.h-content div.content卡片',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.h-content div.content a[href] p[title]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'div.h-content div.content a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析山西省工业和信息化厅主内容厅领导卡片。"""
    try:
        repaired_html = html.encode("latin1").decode("utf-8")
        if len(re.findall(r"[\u4e00-\u9fff]", repaired_html)) > len(re.findall(r"[\u4e00-\u9fff]", html)):
            html = repaired_html
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for duty_node in soup.select("div.h-content div.content a[href] p[title]"):
        link = duty_node.find_parent("a")
        text_parts = [clean_text(part) for part in duty_node.stripped_strings if clean_text(part)]
        if not link or not text_parts:
            continue
        name = text_parts[0].replace(" ", "")
        duty = clean_text(str(duty_node.get("title") or " ".join(text_parts[1:])))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        href = str(link.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("javascript:", "#")):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "主内容p[title]第一段取姓名，title取职务",
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
