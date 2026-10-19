from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1023',
 'domain': 'hrss.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_list_detail_yunnan_hrss_leaders_v1',
 'leader_region_selector': '#content p a[href*="NewsView.aspx"][href*="cid=1132"]',
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
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '列表页仅姓名，改为领导简介名单加定点详情页 title/现任句解析；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#content p a[href*="NewsView.aspx"][href*="cid=1132"]',
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
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩云南人社厅页面中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def load_detail_html(detail_url: str) -> str:
    """在线读取指定领导详情页。"""
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_duty(detail_html: str, name: str) -> str:
    """从详情页 title 字段或“现任”句提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = soup.select_one("p.title")
    if title:
        duty = clean_text(title.get_text(" ", strip=True))
        if duty:
            return duty
    desc = clean_text(" ".join(node.get_text(" ", strip=True) for node in soup.select("p.desc")))
    match = re.search(rf"{re.escape(name)}，.+?现任(?P<duty>.+)$", desc)
    if match:
        return match.group("duty").strip(" ，。；;、")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析云南省人社厅领导简介列表和定点详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；list=#content NewsView cid=1132；detail=p.title_or_desc_现任"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('#content p a[href*="NewsView.aspx"][href*="cid=1132"]'):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(page_url, str(link.get("href", "")))
        duty = extract_duty(load_detail_html(detail_url), name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
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
