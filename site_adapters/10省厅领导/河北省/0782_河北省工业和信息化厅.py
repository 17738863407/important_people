from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0782',
 'domain': 'gxt.hebei.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_inline_hebei_gxt_leader_list_detail_artcontent_line_v1',
 'leader_region_selector': 'a[istitle="true"][href*="/tldjs47/"][title]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[istitle="true"][href*="/tldjs47/"][title]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '原通用详情链把来源、时间、姓名混入职务字段，需限定领导列表和详情正文职务行',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a[istitle="true"][href*="/tldjs47/"][title]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[istitle="true"][href*="/tldjs47/"][title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def compact_text(value: str) -> str:
    """移除网页排版空白，便于处理姓名中间断开的情况。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def load_detail_html(detail_url: str, referer: str) -> str:
    """在线获取领导详情页。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_detail_duty(name: str, detail_html: str) -> str:
    """从详情正文中的“姓名 职务”行提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".artContent") or soup.select_one('[scope="zkhlAisiteArticleContent"]')
    compact_name = compact_text(name)
    for raw_line in (content or soup).stripped_strings:
        line = clean_text(raw_line)
        compact_line = compact_text(line)
        if not compact_line.startswith(compact_name):
            continue
        duty = compact_line[len(compact_name):]
        if duty and not duty.startswith(("来源", "时间")):
            return duty.rstrip("。；")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河北省工业和信息化厅领导列表及详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[istitle="true"][href*="/tldjs47/"][title]'):
        name = compact_text(str(link.get("title") or link.get_text(" ", strip=True)))
        href = str(link.get("href") or "")
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(source_url, href)
        duty = parse_detail_duty(name, load_detail_html(detail_url, source_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "列表页tldjs47领导链接取姓名；详情页.artContent姓名职务行取职务",
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
